"""Fallback TTS provider — chains multiple providers, trying each in order."""

import asyncio

from loguru import logger

from src.tts.base import TTSProvider


class FallbackTTSProvider(TTSProvider):
    """
    A meta-provider that tries a list of TTS providers in order.

    On each call to :meth:`synthesize`, providers are tried sequentially.
    If a provider raises any exception it is logged as a warning and the next
    provider in the chain is attempted.  If every provider fails the last
    exception is re-raised as a :class:`RuntimeError`.

    Example usage::

        provider = FallbackTTSProvider([
            EdgeTTSProvider(),   # tried first
            PiperTTSProvider(),  # local fallback
        ])
    """

    def __init__(self, providers: list[TTSProvider]):
        if not providers:
            raise ValueError("FallbackTTSProvider requires at least one provider")
        self.providers = providers

    async def synthesize(self, text: str, output_path: str, voice: str | None = None) -> str:
        """
        Try each provider in order and return the first successful result.

        Args:
            text: The text to synthesize.
            output_path: Destination path for the .ogg file.
            voice: Optional voice override passed through to each provider.

        Returns:
            output_path returned by the first successful provider.

        Raises:
            RuntimeError: If all providers fail.
        """
        last_exc: Exception | None = None
        for provider in self.providers:
            name = type(provider).__name__
            try:
                result = await provider.synthesize(text, output_path, voice)
                logger.debug("TTS succeeded with provider={}", name)
                return result
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("TTS provider={} failed: {}; trying next", name, exc)
                last_exc = exc

        raise RuntimeError("All TTS providers failed") from last_exc
