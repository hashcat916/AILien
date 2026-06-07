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
# 0.01 works well for most desktop microphones at arm's-length distance.
_SPEECH_RMS_THRESHOLD = 0.01
# Zero-crossing rate threshold: speech has moderate ZCR (< 0.25),
# while pure noise/hums/fans have high ZCR (> 0.4).  This cheap check
# avoids wasting Whisper cycles on non-speech audio.
_SPEECH_ZCR_THRESHOLD = 0.25
# Minimum duration in seconds for a chunk to be worth transcribing.
# Very short clips are almost certainly noise bursts or mic pops.
_MIN_AUDIO_DURATION = 0.3

# Cached WebRTC VAD instance (lazy-loaded on first speech check).
_VAD_INSTANCE = None

# VAD filter statistics (reset on each start)
_VAD_STATS = {
    "total": 0,          # total chunks checked
    "rms_rejected": 0,   # rejected by RMS (too quiet)
    "vad_rejected": 0,   # rejected by WebRTC VAD (no speech)
    "zcr_rejected": 0,   # rejected by ZCR (noise-like)
    "passed": 0,         # passed all filters → sent to Whisper
}
_VAD_STATS_LOCK = threading.Lock()


def reset_vad_stats() -> None:
    """Reset VAD filter statistics (called on each detector start)."""
    with _VAD_STATS_LOCK:
        for key in _VAD_STATS:
            _VAD_STATS[key] = 0


def _log_vad_stats() -> None:
    """Log current VAD filter statistics to the logger."""
    with _VAD_STATS_LOCK:
        t = _VAD_STATS["total"]
        if t == 0:
            return
        rms_pct = _VAD_STATS["rms_rejected"] / t * 100
        vad_pct = _VAD_STATS["vad_rejected"] / t * 100
        zcr_pct = _VAD_STATS["zcr_rejected"] / t * 100
        passed_pct = _VAD_STATS["passed"] / t * 100
    logger.info(
        "VAD filter stats (last %d chunks): "
        "RMS rejected %.0f%% | VAD rejected %.0f%% | "
        "ZCR rejected %.0f%% | Passed to Whisper %.0f%%",
        t, rms_pct, vad_pct, zcr_pct, passed_pct,
    )


def _record_vad_result(result: str) -> None:
    """Record a VAD filter result and log summary every 50 chunks."""
    with _VAD_STATS_LOCK:
        _VAD_STATS["total"] += 1
        _VAD_STATS[result] += 1
    # Log summary every 50 chunks (outside lock to avoid holding it during I/O)
    if _VAD_STATS["total"] >= 50 and _VAD_STATS["total"] % 50 == 0:
        _log_vad_stats()


def _get_vad():
    """Lazy-load and return a cached WebRTC VAD instance."""
    global _VAD_INSTANCE
    if _VAD_INSTANCE is None:
        try:
            import webrtcvad
            _VAD_INSTANCE = webrtcvad.Vad(config.VAD_AGGRESSIVENESS)  # 0-3 (configurable via .env)
        except ImportError:
            _VAD_INSTANCE = False  # Sentinel: VAD not available
    return _VAD_INSTANCE if _VAD_INSTANCE is not False else None


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
        # Sort by descending length so longer, more specific phrases (e.g.
        # "hello there") are checked *before* shorter substrings (e.g.
        # "hello") — otherwise the short match would always swallow the
        # longer one and produce a garbled extracted command.
        self.wake_words = sorted(
            [w.lower() for w in (wake_words or config.AGENT_WAKE_WORDS)],
            key=len,
            reverse=True,
        )
        self.recorder = recorder or AudioRecorder()
        self.chunk_max_duration = chunk_max_duration
        self.chunk_silence_duration = chunk_silence_duration
        self.silence_threshold = silence_threshold
        self._running = False
        self._paused = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the wake word detector in a background thread."""
        reset_vad_stats()
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
        # Log final VAD stats for this session
        _log_vad_stats()

    def pause(self) -> None:
        """Pause listening (e.g. while processing a command or playing TTS)."""
        self._paused.set()

    def resume(self) -> None:
        """Resume listening after a pause."""
        self._paused.clear()

    @staticmethod
    def _has_speech(audio: np.ndarray) -> bool:
        """Three-pass speech pre-filter with per-stage stats recording.

        Order (cheapest first):
          1. RMS energy gate — rejects pure silence instantly (~1 µs).
          2. WebRTC VAD — industry-standard voice activity detection
             (~1 ms per chunk, far more accurate than ZCR).  Falls back
             to ZCR if ``webrtcvad`` is not installed.
          3. Zero-crossing rate — catches high-frequency noise that
             WebRTC might miss (fan hums, keyboard clicks).

        Returns True only if the chunk sounds like human speech.
        """
        if audio.size == 0:
            return False

        # Pass 1: RMS energy gate (cheapest)
        rms = np.sqrt(np.mean(audio ** 2))
        if rms < _SPEECH_RMS_THRESHOLD:
            _record_vad_result("rms_rejected")
            return False

        # Pass 2: WebRTC VAD (fast, accurate, cached instance)
        vad = _get_vad()
        if vad is not None:
            # Convert float32 [-1, 1] → int16 for WebRTC
            audio_int16 = (audio * 32767).astype(np.int16)
            # WebRTC VAD operates on 30 ms frames (480 samples @ 16 kHz)
            FRAME_MS = 30
            frame_size = int(config.AUDIO_SAMPLE_RATE * FRAME_MS / 1000)  # 480
            speech_frames = 0
            total_frames = 0
            for i in range(0, len(audio_int16) - frame_size + 1, frame_size):
                frame = audio_int16[i:i + frame_size].tobytes()
                if vad.is_speech(frame, config.AUDIO_SAMPLE_RATE):
                    speech_frames += 1
                total_frames += 1
            # Require at least 2 speech frames (~60 ms) before passing
            if total_frames > 0 and speech_frames < 2:
                _record_vad_result("vad_rejected")
                return False

        # Pass 3: Zero-crossing rate (catches noise WebRTC might miss)
        signs = np.sign(audio)
        zcr = np.mean(np.abs(np.diff(signs))) / 2
        if zcr >= _SPEECH_ZCR_THRESHOLD:
            _record_vad_result("zcr_rejected")
            return False

        _record_vad_result("passed")
        return True

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

    Uses the **Whisper-based** ``WakeWordDetector`` which transcribes audio
    chunks and checks for any activation phrase in `AGENT_WAKE_WORDS`.
    This supports *arbitrary* phrases ("hello", "what's up", "hey there",
    etc.) — unlike dedicated engines (Porcupine, openWakeWord) which are
    limited to specific pre-trained or pre-configured keywords.

    The detector exposes start / stop / pause / resume so callers don't
    need to know which engine is running underneath.
    """
    wake_words = wake_words or config.AGENT_WAKE_WORDS

    # 1. Whisper-based detector (supports any wake word / activation phrase)
    #    Preferred because dedicated engines (Porcupine, openWakeWord) only
    #    detect the specific phrases they were trained / configured for and
    #    can't handle arbitrary conversational starters like "hello" or "hi".
    logger.info(
        "Using Whisper-based wake word detector (%d activation phrases)",
        len(wake_words),
    )
    return WakeWordDetector(
        transcriber=transcriber,
        callback=callback,
        recorder=recorder,
        wake_words=wake_words,
        chunk_max_duration=chunk_max_duration,
        chunk_silence_duration=chunk_silence_duration,
        silence_threshold=silence_threshold,
    )

