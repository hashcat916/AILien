"""Audio recording module using sounddevice."""
import threading
import time
from collections import deque

import numpy as np
import sounddevice as sd

import config


class AudioRecorder:
    """Records audio from the microphone with silence-based stop."""

    def __init__(self):
        self._recording = False
        self._frames: deque[np.ndarray] = deque()
        self._stream = None
        self._lock = threading.Lock()

    def _callback(self, indata: np.ndarray, _frames: int, _time_info: dict, _status: sd.CallbackFlags) -> None:
        """SoundDevice callback that appends audio chunks."""
        if self._recording:
            self._frames.append(indata.copy())

    def start(self) -> None:
        """Start recording audio."""
        try:
            self._frames.clear()
            self._recording = True
            self._stream = sd.InputStream(
                samplerate=config.AUDIO_SAMPLE_RATE,
                channels=config.AUDIO_CHANNELS,
                blocksize=config.AUDIO_BLOCK_SIZE,
                dtype=np.float32,
                callback=self._callback,
            )
            self._stream.start()
        except Exception as exc:
            self._recording = False
            raise RuntimeError(f"Failed to start audio recording: {exc}. Is a microphone available?") from exc

    def stop(self) -> np.ndarray:
        """Stop recording and return the recorded audio as a single array."""
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self._frames:
            return np.array([], dtype=np.float32)
        return np.concatenate(list(self._frames), axis=0).flatten()

    def record_until_silence(
        self,
        silence_threshold: float = config.AUDIO_SILENCE_THRESHOLD,
        silence_duration: float = config.AUDIO_SILENCE_DURATION,
        max_duration: float = config.AUDIO_RECORD_TIMEOUT,
    ) -> np.ndarray:
        """
        Record audio until silence is detected or max duration is reached.
        Returns the recorded audio array.
        """
        with self._lock:
            self.start()
            silence_start: float | None = None
            record_start = time.time()
            try:
                while True:
                    time.sleep(0.1)
                    elapsed = time.time() - record_start
                    if elapsed > max_duration:
                        break
                    # Check recent audio for silence
                    if len(self._frames) >= 3:
                        recent = np.concatenate(list(self._frames)[-3:], axis=0).flatten()
                        rms = np.sqrt(np.mean(recent**2))
                        if rms < silence_threshold:
                            if silence_start is None:
                                silence_start = time.time()
                            elif time.time() - silence_start > silence_duration:
                                break
                        else:
                            silence_start = None
            finally:
                audio = self.stop()
            return audio

    def record_fixed(self, duration: float) -> np.ndarray:
        """Record audio for a fixed duration."""
        with self._lock:
            self.start()
            time.sleep(duration)
            return self.stop()
