"""Abstract base class for Text-to-Speech providers."""

from abc import ABC, abstractmethod


class TTSProvider(ABC):
    """Abstract base class for Text-to-Speech synthesis providers."""

    @abstractmethod
    async def synthesize(self, text: str, output_path: str, voice: str | None = None) -> str:
        """
        Synthesize text to speech and write to output_path.

        Args:
            text: The text to synthesize.
            output_path: Path where the output audio file should be written.
            voice: Optional voice override; falls back to provider default.

        Returns:
            The output_path of the written file.
        """
