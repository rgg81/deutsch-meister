"""Local Whisper STT provider using faster-whisper."""

from pathlib import Path

import anyio
from loguru import logger

from src.stt.base import STTProvider


class WhisperSTTProvider(STTProvider):
    """
    Speech-to-Text provider using faster-whisper (local inference).

    Runs the Whisper model locally via CTranslate2. The model is downloaded
    automatically from HuggingFace on first use.

    Supported model sizes: tiny (~75 MB), base (~142 MB), small (~466 MB).
    The ``base`` model offers a good balance of speed and German accuracy.
    """

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None

    def _load_model(self):
        """Lazy-load the WhisperModel (downloads on first use)."""
        if self._model is None:
            from faster_whisper import WhisperModel

            logger.info("Loading faster-whisper model: {}", self.model_size)
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    async def transcribe(self, file_path: str | Path) -> str:
        """
        Transcribe an audio file using the local Whisper model.

        Args:
            file_path: Path to the audio file.

        Returns:
            Transcribed text, or empty string on failure.
        """
        path = Path(file_path)
        if not path.exists():
            logger.error("Audio file not found: {}", file_path)
            return ""

        try:
            def _run_transcription():
                model = self._load_model()
                segments, _ = model.transcribe(str(path))
                return " ".join(seg.text for seg in segments).strip()

            return await anyio.to_thread.run_sync(_run_transcription)
        except Exception:
            logger.exception("Whisper transcription error")
            return ""
