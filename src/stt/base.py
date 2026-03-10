"""Abstract base class for Speech-to-Text providers."""

from abc import ABC, abstractmethod
from pathlib import Path


class STTProvider(ABC):
    """Abstract base class for Speech-to-Text transcription providers."""

    @abstractmethod
    async def transcribe(self, file_path: str | Path) -> str:
        """
        Transcribe an audio file to text.

        Args:
            file_path: Path to the audio file.

        Returns:
            Transcribed text, or empty string on failure.
        """
