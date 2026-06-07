"""Fast wake word detection using openWakeWord.

Replaces the old Whisper-based approach (which transcribed every audio chunk)
with openWakeWord's lightweight neural network — ~50ms inference per frame
instead of seconds per chunk.  openWakeWord runs 100% offline with no API keys.

The detector opens a sounddevice InputStream only when active (not paused),
so it won't conflict with the AudioRecorder used for follow-up commands.
"""

import logging
import threading
import time

import numpy as np

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

import config

logger = logging.getLogger("agent")

# Model names shipped with openwakeword (see openwakeword.Model.list_models)


def is_available() -> bool:
    """Return True if openwakeword can be loaded successfully."""
    try:
        import openwakeword  # noqa: F401
        return True
    except ImportError:
        return False


class OpenWakeWordDetector:
    """Continuous wake word listener backed by openWakeWord.

    Interface matches ``WakeWordDetector`` (start / stop / pause / resume /
    callback) so it can be used as a drop-in replacement in ``main.py``.

    When the wake word is detected the *callback* is fired with an empty
    string — the callers in ``main.py`` already handle the follow-up
    record + transcribe flow.
    """

    def __init__(
        self,
        callback,
        *,
        model_name: str = "hey_jarvis",
        threshold: float = 0.5,
        frame_length: int = 1280,       # 80 ms @ 16 kHz
        debounce_seconds: float = 1.5,
    ) -> None:
        self.callback = callback
        self.model_name = model_name
        self.threshold = threshold
        self.frame_length = frame_length
        self.debounce_seconds = debounce_seconds

        self._running = False
        self._paused = threading.Event()
        self._thread: threading.Thread | None = None
        self._oww_model = None

    # ------------------------------------------------------------------
    # Public interface (matches WakeWordDetector)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the wake word detector in a background thread."""
        if not is_available():
            logger.warning("openWakeWord not available — install with: pip install openwakeword")
            return
        self._running = True
        self._paused.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the detector and join the background thread."""
        self._running = False
        self._paused.clear()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        self._oww_model = None

    def pause(self) -> None:
        """Pause listening (closes the audio stream so the recorder can use it)."""
        self._paused.set()

    def resume(self) -> None:
        """Resume listening after a pause."""
        self._paused.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_model(self) -> bool:
        """Lazy-load the openWakeWord model.  Returns True on success."""
        if self._oww_model is not None:
            return True
        try:
            import openwakeword
            from openwakeword.model import Model

            # Look up the pre-trained model file path by name
            model_key = self.model_name.lower()
            model_info = openwakeword.models.get(model_key)
            if model_info is None:
                logger.error(
                    "OpenWakeWord model '%s' not found. Available: %s",
                    model_key, list(openwakeword.models.keys()),
                )
                return False

            # model_info is a dict: {"model_path": "/path/to/model.onnx"}
            model_path = model_info["model_path"] if isinstance(model_info, dict) else str(model_info)

            logger.info(
                "Loading openWakeWord model '%s' (first run may download ~5MB)...",
                model_key,
            )
            self._oww_model = Model(wakeword_model_paths=[model_path])
            logger.info("OpenWakeWord model '%s' loaded — say 'Hey Jarvis' to wake me", model_key)
            return True
        except Exception as exc:
            logger.error("Failed to load openWakeWord model: %s", exc)
            return False

    def _run(self) -> None:
        """Main listening loop — opens a stream, feeds frames to openWakeWord."""
        if not self._load_model():
            return

        while self._running:
            if self._paused.is_set():
                time.sleep(0.1)
                continue

            # Open a fresh InputStream.  It's closed every time we pause so
            # the AudioRecorder can use the mic without conflict.
            try:
                stream = sd.InputStream(
                    samplerate=config.AUDIO_SAMPLE_RATE,
                    channels=config.AUDIO_CHANNELS,
                    dtype=np.float32,
                    blocksize=self.frame_length,
                )
                stream.start()
            except Exception as exc:
                logger.warning("Failed to open mic stream: %s", exc)
                time.sleep(1.0)
                continue

            try:
                while self._running and not self._paused.is_set():
                    frame, _ = stream.read(self.frame_length)
                    frame = frame.flatten()

                    try:
                        prediction = self._oww_model.predict(frame)
                    except Exception:
                        continue

                    for _name, score in prediction.items():
                        if score >= self.threshold:
                            logger.info(
                                "Wake word detected (%.3f ≥ %.2f)", score, self.threshold
                            )
                            try:
                                self.callback("")
                            except Exception:
                                logger.exception("Wake word callback failed")
                            time.sleep(self.debounce_seconds)
                            break
            finally:
                stream.stop(ignore_errors=True)
                stream.close(ignore_errors=True)
