"""Local speech-to-text using faster-whisper."""
import io
import wave
from pathlib import Path

import numpy as np

import config


class WhisperTranscriber:
    """Transcribes audio to text using a local Whisper model."""

    def __init__(self) -> None:
        self._model = None
        self._loaded = False

    def _load_model(self) -> None:
        """Lazy-load the Whisper model."""
        if self._loaded:
            return
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. "
                "Run: pip install faster-whisper"
            ) from exc

        print(f"[dim]Loading Whisper model '{config.WHISPER_MODEL}'...[/dim]")
        self._model = WhisperModel(
            config.WHISPER_MODEL,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_COMPUTE_TYPE,
            download_root=str(config.CACHE_DIR / "models"),
        )
        self._loaded = True
        print("[dim]Whisper model loaded.[/dim]")

    def _array_to_wav_bytes(self, audio: np.ndarray) -> bytes:
        """Convert a float32 numpy array to WAV bytes."""
        # Normalize to int16
        audio = np.clip(audio, -1.0, 1.0)
        audio_int16 = (audio * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(config.AUDIO_CHANNELS)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(config.AUDIO_SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())
        return buf.getvalue()

    def transcribe(self, audio: np.ndarray, language: str | None = "en") -> str:
        """
        Transcribe audio array to text.
        Returns the transcribed text.
        """
        if audio.size == 0:
            return ""
        self._load_model()
        wav_bytes = self._array_to_wav_bytes(audio)
        # VAD filter is disabled by default — it was too aggressive and filtered out
        # all audio on many systems. Enable it via WHISPER_VAD_FILTER=true if you
        # find it works well with your microphone and environment.
        segments, _ = self._model.transcribe(
            io.BytesIO(wav_bytes),
            language=language,
            vad_filter=config.WHISPER_VAD_FILTER,
        )
        text = " ".join(segment.text.strip() for segment in segments)
        return text.strip()
