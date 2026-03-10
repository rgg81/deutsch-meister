"""Fallback STT provider that chains multiple providers."""

from pathlib import Path

from loguru import logger

from src.stt.base import STTProvider


class FallbackSTTProvider(STTProvider):
    """
    STT provider that tries a list of providers in order.

    Iterates through the given providers, returning the first non-empty
    transcription result. If all providers fail or return empty strings,
    returns an empty string.
    """

    def __init__(self, providers: list[STTProvider]):
        self.providers = providers

    async def transcribe(self, file_path: str | Path) -> str:
        """
        Transcribe an audio file, falling back through the provider chain.

        Args:
            file_path: Path to the audio file.

        Returns:
            Transcribed text from the first successful provider, or empty string.
        """
        for provider in self.providers:
            try:
                result = await provider.transcribe(file_path)
                if result:
                    return result
            except Exception:
                logger.exception(
                    "Provider {} failed, trying next", provider.__class__.__name__
                )
                continue
        return ""
