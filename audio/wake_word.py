"""Wake word detection using continuous audio listening."""
import logging
import threading
import time

import numpy as np

import config
from audio.recorder import AudioRecorder
from audio.transcriber import WhisperTranscriber

logger = logging.getLogger("agent")

# Minimum audio level (RMS) to consider as potential speech — ignores
# ambient noise / silence so we don't waste CPU transcribing empty chunks.
_SPEECH_RMS_THRESHOLD = 0.005
# Minimum duration in seconds for a chunk to be worth transcribing.
# Very short clips are almost certainly noise bursts or mic pops.
_MIN_AUDIO_DURATION = 0.3


class WakeWordDetector:
    """Listens continuously for a wake word and triggers a callback with the command text."""

    def __init__(
        self,
        transcriber: WhisperTranscriber,
        callback,
        recorder: AudioRecorder | None = None,
        wake_words: list[str] | None = None,
        chunk_max_duration: float = 4.0,
        chunk_silence_duration: float = 0.8,
        silence_threshold: float = config.AUDIO_SILENCE_THRESHOLD,
    ):
        self.transcriber = transcriber
        self.callback = callback
        self.wake_words = [w.lower() for w in (wake_words or config.AGENT_WAKE_WORDS)]
        self.recorder = recorder or AudioRecorder()
        self.chunk_max_duration = chunk_max_duration
        self.chunk_silence_duration = chunk_silence_duration
        self.silence_threshold = silence_threshold
        self._running = False
        self._paused = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the wake word detector in a background thread."""
        self._running = True
        self._paused.clear()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the wake word detector."""
        self._running = False
        self._paused.clear()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def pause(self) -> None:
        """Pause listening (e.g. while processing a command or playing TTS)."""
        self._paused.set()

    def resume(self) -> None:
        """Resume listening after a pause."""
        self._paused.clear()

    @staticmethod
    def _has_speech(audio: np.ndarray) -> bool:
        """Quick energy check: return True if the audio chunk has enough
        RMS energy to be worth transcribing."""
        if audio.size == 0:
            return False
        rms = np.sqrt(np.mean(audio ** 2))
        return rms >= _SPEECH_RMS_THRESHOLD

    def _extract_command(self, text: str, wake_word: str) -> str:
        """Extract the command text that follows the wake word."""
        idx = text.lower().find(wake_word)
        if idx == -1:
            return ""
        after = text[idx + len(wake_word):].strip()
        # Strip common separators
        for sep in [",", ".", "!", "?", " "]:
            if after.startswith(sep):
                after = after[1:].strip()
        return after

    def _listen_loop(self) -> None:
        """Main listening loop."""
        while self._running:
            if self._paused.is_set():
                time.sleep(0.2)
                continue
            try:
                audio = self.recorder.record_until_silence(
                    silence_threshold=self.silence_threshold,
                    silence_duration=self.chunk_silence_duration,
                    max_duration=self.chunk_max_duration,
                )
            except RuntimeError:
                # Microphone unavailable
                time.sleep(1.0)
                continue

            # Skip empty / very short audio
            if audio.size == 0:
                continue
            duration = audio.size / config.AUDIO_SAMPLE_RATE
            if duration < _MIN_AUDIO_DURATION:
                continue

            # Energy gate: skip silent chunks so we don't burn CPU
            # transcribing ambient noise.
            if not self._has_speech(audio):
                continue

            text = self.transcriber.transcribe(audio)
            if not text:
                continue

            text_lower = text.lower().strip()
            for wake_word in self.wake_words:
                if wake_word in text_lower:
                    command_text = self._extract_command(text, wake_word)
                    try:
                        self.callback(command_text)
                    except Exception:
                        logger.exception("Wake word callback failed")
                    # Debounce: sleep so that TTS output or ambient speech
                    # doesn't immediately re-trigger.  The main thread also
                    # calls pause() via the callback, so we don't touch the
                    # Event here to avoid racing with it.
                    time.sleep(1.5)
                    break


def create_detector(
    transcriber: WhisperTranscriber,
    callback,
    recorder: AudioRecorder | None = None,
    wake_words: list[str] | None = None,
    chunk_max_duration: float = 4.0,
    chunk_silence_duration: float = 0.8,
    silence_threshold: float = config.AUDIO_SILENCE_THRESHOLD,
):
    """Create the best available wake word detector.

    Priority:

    1. **Porcupine** (if a PICOVOICE_ACCESS_KEY + keyword paths are
       configured) — supports *custom* wake words like "hey alien".
       Requires ``.ppn`` files from the Picovoice Console.
    2. **openWakeWord** (if installed) — fast, lightweight, dedicated
       wake word engine using pre-trained models ("hey jarvis").
    3. **Whisper-based** ``WakeWordDetector`` — slower but works with
       zero extra dependencies and supports any wake word text.

    All three expose the same interface (start / stop / pause / resume)
    so callers don't need to know which one is running underneath.
    """
    # 1. Try Porcupine (custom wake words)
    try:
        from audio.porcupine_detector import PorcupineDetector, is_available, has_custom_keywords

        if is_available() and has_custom_keywords():
            logger.info("Using Porcupine detector (custom wake words)")
            return PorcupineDetector(callback=callback)
    except Exception as exc:
        logger.debug("Porcupine not available: %s", exc)

    # 2. Try openWakeWord (fast, pre-trained models)
    try:
        from audio.openwakeword_detector import OpenWakeWordDetector, is_available

        if is_available():
            logger.info("Using openWakeWord detector (fast, pre-trained wake word engine)")
            return OpenWakeWordDetector(callback=callback)
    except Exception as exc:
        logger.debug("openWakeWord not available, falling back to Whisper-based detector: %s", exc)

    # 3. Fallback: Whisper-based (works anywhere, supports any text)
    logger.info("Using Whisper-based wake word detector")
    return WakeWordDetector(
        transcriber=transcriber,
        callback=callback,
        recorder=recorder,
        wake_words=wake_words,
        chunk_max_duration=chunk_max_duration,
        chunk_silence_duration=chunk_silence_duration,
        silence_threshold=silence_threshold,
    )
