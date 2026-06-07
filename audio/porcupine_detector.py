"""Wake word detection using Picovoice Porcupine.

Porcupine supports **custom wake words** (unlike openWakeWord's fixed
pre-trained set) by using ``.ppn`` model files generated at the
`Picovoice Console <https://console.picovoice.ai/>`_.

Setup (one-time):
  1. Sign up at https://console.picovoice.ai/ (free tier)
  2. Create custom wake words (e.g. "hey alien", "hey ailien")
     and download the Linux ``.ppn`` files.
  3. Place the ``.ppn`` files in the project (e.g. ``wake_words/``).
  4. Set in ``.env``:

     PICOVOICE_ACCESS_KEY=your_access_key_here
     PICOVOICE_KEYWORD_PATHS=wake_words/hey_alien.ppn,wake_words/hey_ailien.ppn
     PICOVOICE_SENSITIVITIES=0.5,0.7       # optional, per-keyword sensitivity

The detector opens a sounddevice InputStream only when active (not paused),
so it won't conflict with the AudioRecorder used for follow-up commands.
"""

import logging
import threading
import time
from pathlib import Path

import numpy as np

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

import config

logger = logging.getLogger("agent")


def is_available() -> bool:
    """Return True if pvporcupine is installed."""
    try:
        import pvporcupine  # noqa: F401
        return True
    except ImportError:
        return False


def has_custom_keywords() -> bool:
    """Return True if the user has configured custom wake word keywords."""
    access_key = config.PICOVOICE_ACCESS_KEY
    keyword_paths = config.PICOVOICE_KEYWORD_PATHS
    return bool(access_key) and bool(keyword_paths)


class PorcupineDetector:
    """Wake word listener backed by Picovoice Porcupine.

    Supports custom wake words via ``.ppn`` model files generated at
    the Picovoice Console.

    Interface matches ``WakeWordDetector`` (start / stop / pause / resume /
    callback) so it can be used as a drop-in replacement.
    """

    def __init__(
        self,
        callback,
        *,
        access_key: str | None = None,
        keyword_paths: list[str] | None = None,
        sensitivities: list[float] | None = None,
        debounce_seconds: float = 1.5,
    ) -> None:
        self.callback = callback
        self.access_key = access_key or config.PICOVOICE_ACCESS_KEY
        self.keyword_paths = keyword_paths or config.PICOVOICE_KEYWORD_PATHS
        self.sensitivities = sensitivities
        self.debounce_seconds = debounce_seconds

        self._running = False
        self._paused = threading.Event()
        self._thread: threading.Thread | None = None
        self._porcupine = None
        self._frame_length = 512  # default; updated after Porcupine init

    # ------------------------------------------------------------------
    # Public interface (matches WakeWordDetector)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the wake word detector in a background thread."""
        if not is_available():
            logger.warning("Porcupine not available — install with: pip install pvporcupine")
            return
        if not self.access_key or not self.keyword_paths:
            logger.warning(
                "Porcupine keywords not configured. Set PICOVOICE_ACCESS_KEY "
                "and PICOVOICE_KEYWORD_PATHS in .env"
            )
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
        self._close_porcupine()

    def pause(self) -> None:
        """Pause listening (closes the audio stream so the recorder can use it)."""
        self._paused.set()

    def resume(self) -> None:
        """Resume listening after a pause."""
        self._paused.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _init_porcupine(self) -> bool:
        """Initialize the Porcupine engine. Returns True on success."""
        if self._porcupine is not None:
            return True
        try:
            import pvporcupine

            # Resolve .ppn paths relative to the project directory
            resolved_paths = []
            for p in self.keyword_paths:
                path = Path(p)
                if not path.is_absolute():
                    path = config.PROJECT_DIR / path
                if not path.exists():
                    logger.error("Porcupine keyword file not found: %s", path)
                    return False
                resolved_paths.append(str(path.resolve()))

            kw_count = len(resolved_paths)
            kw_names = [Path(p).stem for p in resolved_paths]
            logger.info(
                "Initializing Porcupine with %d keyword(s): %s",
                kw_count, kw_names,
            )

            kwargs = {
                "access_key": self.access_key,
                "keyword_paths": resolved_paths,
            }
            if self.sensitivities:
                kwargs["sensitivities"] = self.sensitivities

            self._porcupine = pvporcupine.create(**kwargs)
            self._frame_length = self._porcupine.frame_length

            logger.info("Porcupine ready (frame_length=%d)", self._frame_length)
            return True
        except Exception as exc:
            logger.error("Failed to initialize Porcupine: %s", exc)
            return False

    def _close_porcupine(self) -> None:
        """Release the Porcupine handle."""
        if self._porcupine is not None:
            try:
                self._porcupine.delete()
            except Exception:
                pass
            self._porcupine = None

    def _run(self) -> None:
        """Main listening loop — opens a stream, feeds frames to Porcupine."""
        if not self._init_porcupine():
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
                    blocksize=self._frame_length,
                )
                stream.start()
            except Exception as exc:
                logger.warning("Failed to open mic stream: %s", exc)
                time.sleep(1.0)
                continue

            try:
                while self._running and not self._paused.is_set():
                    frame, _ = stream.read(self._frame_length)
                    frame = frame.flatten()

                    # Porcupine expects 16-bit PCM, convert from float32
                    frame_int16 = (frame * 32767).astype(np.int16)

                    keyword_index = self._porcupine.process(frame_int16)
                    if keyword_index >= 0:
                        kw_names = [Path(p).stem for p in self.keyword_paths]
                        kw_name = kw_names[keyword_index] if keyword_index < len(kw_names) else f"keyword_{keyword_index}"
                        logger.info("Wake word detected: '%s' (index=%d)", kw_name, keyword_index)
                        try:
                            self.callback("")
                        except Exception:
                            logger.exception("Wake word callback failed")
                        time.sleep(self.debounce_seconds)
                        break
            finally:
                stream.stop(ignore_errors=True)
                stream.close(ignore_errors=True)
