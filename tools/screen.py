"""Screen capture and OCR tools.

OCR engines supported (in order of preference):
1. Tesseract (via pytesseract) — fast, lightweight, great for clean screen text
2. EasyOCR — slower but better at noisy/fancy fonts (fallback)

Configure via ``config.OCR_ENGINE`` (``tesseract``, ``easyocr``, or ``auto``).
"""

import base64
import hashlib
import io
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

import config
from tools import tool

logger = logging.getLogger("agent")

# ---------------------------------------------------------------------------
# Lazy-loaded OCR engines
# ---------------------------------------------------------------------------

_TESSERACT_AVAILABLE: bool | None = None
_EASYOCR_READER: Any = None  # type: ignore[valid-type]

# Simple LRU cache: image_hash -> (result, timestamp)
_OCR_CACHE: dict[str, tuple[str, float]] = {}
_OCR_CACHE_MAX = 16
_OCR_CACHE_TTL = 2.0  # seconds — screen changes fast


def _check_tesseract() -> bool:
    """Check if tesseract is available on the system."""
    global _TESSERACT_AVAILABLE
    if _TESSERACT_AVAILABLE is None:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            _TESSERACT_AVAILABLE = True
        except Exception:
            _TESSERACT_AVAILABLE = False
    return _TESSERACT_AVAILABLE


def _get_easyocr_reader():
    """Lazy-load and cache the EasyOCR reader."""
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        import easyocr
        _EASYOCR_READER = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _EASYOCR_READER


# ---------------------------------------------------------------------------
# Screen capture utilities
# ---------------------------------------------------------------------------


@dataclass
class ScreenCapture:
    """Holds a screen capture and its metadata."""

    pil_image: Image.Image
    numpy_array: np.ndarray
    width: int
    height: int
    image_hash: str = field(init=False)

    def __post_init__(self):
        self.image_hash = hashlib.md5(
            self.numpy_array.tobytes()
        ).hexdigest()


def _capture_screen(region: dict | None = None) -> ScreenCapture:
    """Capture the screen (or a region) and return a ScreenCapture object."""
    import mss

    with mss.mss() as sct:
        if region:
            monitor = region
        else:
            monitor = sct.monitors[0]

        img = sct.grab(monitor)
        arr = np.array(img)
        pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
        width, height = img.size

    return ScreenCapture(
        pil_image=pil_img,
        numpy_array=arr,
        width=width,
        height=height,
    )


def _capture_screen_b64() -> tuple[str, ScreenCapture]:
    """Capture the screen, return (base64_jpeg, ScreenCapture)."""
    cap = _capture_screen()
    # Resize for vision API (keep aspect, max 1280 wide)
    cap.pil_image.thumbnail((1280, 720))
    buf = io.BytesIO()
    cap.pil_image.save(buf, format="JPEG", quality=60)
    return base64.b64encode(buf.getvalue()).decode("utf-8"), cap


def _parse_region(region_str: str, screen_w: int, screen_h: int) -> dict:
    """Parse a region string into an mss-compatible monitor dict.

    Accepts:
    - ``\"x,y,w,h\"`` — pixel coordinates
    - A named preset from ``config.OCR_REGION_PRESETS``
    """
    # Check named presets first
    preset = config.OCR_REGION_PRESETS.get(region_str.lower().strip())
    if preset is not None:
        return {
            "top": int(preset["top"] * screen_h),
            "left": int(preset["left"] * screen_w),
            "width": int(preset["width"] * screen_w),
            "height": int(preset["height"] * screen_h),
        }

    # Parse as "x,y,w,h"
    try:
        parts = [int(p.strip()) for p in region_str.split(",")]
        if len(parts) == 4:
            return {
                "left": parts[0],
                "top": parts[1],
                "width": parts[2],
                "height": parts[3],
            }
    except ValueError:
        pass

    raise ValueError(
        f"Invalid region: {region_str!r}. Use 'x,y,w,h' or a named preset: "
        + ", ".join(config.OCR_REGION_PRESETS.keys())
    )


# ---------------------------------------------------------------------------
# OCR engines
# ---------------------------------------------------------------------------


def _ocr_tesseract(image: np.ndarray | Image.Image) -> list[dict]:
    """Run Tesseract OCR, return list of {text, confidence, bbox}."""
    import pytesseract

    if isinstance(image, np.ndarray):
        pil_img = Image.fromarray(image)
    else:
        pil_img = image

    data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)

    results: list[dict] = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf = float(data["conf"][i])
        if text and conf >= config.OCR_CONFIDENCE_THRESHOLD:
            results.append({
                "text": text,
                "confidence": conf,
                "bbox": (
                    data["left"][i],
                    data["top"][i],
                    data["left"][i] + data["width"][i],
                    data["top"][i] + data["height"][i],
                ),
            })

    return results


def _ocr_easyocr(image: np.ndarray) -> list[dict]:
    """Run EasyOCR, return list of {text, confidence, bbox}."""
    reader = _get_easyocr_reader()
    raw = reader.readtext(image)
    results: list[dict] = []
    for bbox, text, confidence in raw:
        if confidence * 100 >= config.OCR_CONFIDENCE_THRESHOLD:
            # bbox is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] — simplify to corners
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            results.append({
                "text": str(text).strip(),
                "confidence": round(confidence * 100, 1),
                "bbox": (min(xs), min(ys), max(xs), max(ys)),
            })
    return results


# ---------------------------------------------------------------------------
# Main OCR function
# ---------------------------------------------------------------------------


def _get_cache_key(cap: ScreenCapture, engine: str, region: str | None) -> str:
    """Generate a cache key from the image hash + OCR params."""
    return f"{cap.image_hash}:{engine}:{region or 'full'}"


def _check_cache(key: str) -> str | None:
    """Return cached OCR result if still fresh, else None."""
    global _OCR_CACHE
    entry = _OCR_CACHE.get(key)
    if entry is None:
        return None
    result, timestamp = entry
    if time.time() - timestamp > _OCR_CACHE_TTL:
        del _OCR_CACHE[key]
        return None
    return result


def _set_cache(key: str, result: str) -> None:
    """Store OCR result in cache, evicting oldest if full."""
    global _OCR_CACHE
    if len(_OCR_CACHE) >= _OCR_CACHE_MAX:
        # Evict oldest entry
        oldest_key = min(_OCR_CACHE, key=lambda k: _OCR_CACHE[k][1])
        del _OCR_CACHE[oldest_key]
    _OCR_CACHE[key] = (result, time.time())


def _format_ocr_results(results: list[dict]) -> str:
    """Format OCR results into a human-readable string."""
    if not results:
        return "No text detected on screen."

    # Group by rough y-position (reading order)
    results.sort(key=lambda r: (r["bbox"][1], r["bbox"][0]))

    show_conf = config.OCR_SHOW_CONFIDENCE

    lines: list[str] = []
    for r in results:
        if show_conf:
            lines.append(f"{r['text']}  [{r['confidence']:.0f}%]")
        else:
            lines.append(r["text"])

    summary = f"Detected {len(results)} text elements"
    return summary + ":\n" + "\n".join(lines)


def _run_ocr(cap: ScreenCapture, engine: str = "auto") -> str:
    """Run OCR on a screen capture, returning formatted text.

    Args:
        cap: The screen capture to analyze.
        engine: ``\"tesseract\"``, ``\"easyocr\"``, or ``\"auto\"`` (prefer tesseract,
                fall back to easyocr).
    """
    cache_key = _get_cache_key(cap, engine, None)
    cached = _check_cache(cache_key)
    if cached is not None:
        return cached

    results: list[dict] = []

    if engine == "auto":
        # Try Tesseract first (fast), fall back to EasyOCR if no results or unavailable
        if _check_tesseract():
            results = _ocr_tesseract(cap.pil_image)
            if not results:
                logger.debug("Tesseract returned no text, trying EasyOCR...")
        if not results:
            try:
                results = _ocr_easyocr(cap.numpy_array)
            except Exception as exc:
                logger.warning("EasyOCR fallback failed: %s", exc)
    elif engine == "tesseract":
        if not _check_tesseract():
            return "Tesseract is not installed. Install with: sudo apt-get install tesseract-ocr"
        results = _ocr_tesseract(cap.pil_image)
    elif engine == "easyocr":
        try:
            results = _ocr_easyocr(cap.numpy_array)
        except Exception as exc:
            return f"EasyOCR failed: {exc}"
    else:
        return f"Unknown OCR engine: {engine}. Use 'tesseract', 'easyocr', or 'auto'."

    formatted = _format_ocr_results(results)
    _set_cache(cache_key, formatted)
    return formatted


# ---------------------------------------------------------------------------
# Registered tools
# ---------------------------------------------------------------------------


@tool(
    name="take_screenshot",
    description=(
        "Take a screenshot of the current screen, analyze it with a vision model, "
        "and return a detailed text description of what is visible. "
        "Use this to understand the UI state before interacting with on-screen elements."
    ),
    params={
        "save_path": {
            "type": "string",
            "description": "Optional path to save the screenshot file",
        },
    },
    required=[],
)
def take_screenshot(save_path: str | None = None) -> str:
    """Take a screenshot, analyze with vision, and return a description.

    Falls back through: cloud vision → OCR → plain screenshot notification.
    """
    b64, cap = _capture_screen_b64()

    # Save to disk if requested
    if save_path:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        cap.pil_image.save(path, format="PNG")

    # 1. Cloud vision analysis
    try:
        from llm.cloud_client import get_cloud_client
        vision = get_cloud_client()
        description = vision.analyze_image(b64)
        if description and not description.startswith("["):
            return f"[Screenshot Analysis] {description}"
    except Exception as exc:
        logger.debug("Cloud vision failed: %s", exc)

    # 2. OCR fallback
    try:
        ocr_text = _run_ocr(cap, engine=config.OCR_ENGINE)
        if ocr_text and "No text detected" not in ocr_text:
            return f"[Screenshot — OCR] {ocr_text}"
    except Exception as exc:
        logger.debug("OCR fallback failed: %s", exc)

    # 3. Plain fallback
    return (
        "[Screenshot captured. Vision analysis and OCR are unavailable. "
        "Consider checking your API key or vision model availability.]"
    )


@tool(
    name="read_screen_text",
    description=(
        "Use OCR to read text visible on the screen. "
        "Returns detected text with optional confidence scores. "
        "Specify a region as 'x,y,w,h' in pixels or use a named preset: "
        + ", ".join(config.OCR_REGION_PRESETS.keys())
    ),
    params={
        "region": {
            "type": "string",
            "description": (
                "Region to read: pixel coordinates 'x,y,w,h' or a named preset "
                f"({', '.join(config.OCR_REGION_PRESETS.keys())}). "
                "If omitted, reads the full screen."
            ),
        },
        "engine": {
            "type": "string",
            "description": "OCR engine: 'tesseract' (fast), 'easyocr' (accurate), or 'auto' (default)",
            "enum": ["auto", "tesseract", "easyocr"],
        },
    },
    required=[],
)
def read_screen_text(
    region: str | None = None,
    engine: str | None = None,
) -> str:
    """OCR text from the screen.

    Args:
        region: Optional region as ``\"x,y,w,h\"`` or a named preset.
        engine: OCR engine to use (default from config).
    """
    engine = engine or config.OCR_ENGINE

    try:
        import mss
    except ImportError:
        return "OCR unavailable: mss is not installed. Run: pip install mss"

    # Capture the screen once only
    full_cap = _capture_screen()

    if region:
        try:
            region_def = _parse_region(region, full_cap.width, full_cap.height)
        except ValueError as exc:
            return str(exc)
        # Crop the already-captured image instead of re-capturing
        x, y, w, h = region_def["left"], region_def["top"], region_def["width"], region_def["height"]
        cropped_np = full_cap.numpy_array[y:y+h, x:x+w]
        cropped_pil = Image.fromarray(cropped_np)
        cap = ScreenCapture(pil_image=cropped_pil, numpy_array=cropped_np, width=w, height=h)
    else:
        cap = full_cap

    return _run_ocr(cap, engine=engine)
