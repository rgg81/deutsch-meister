"""TTS provider package with factory function."""

from src.tts.base import TTSProvider
from src.tts.edge import EdgeTTSProvider


def create_tts_provider(config: dict) -> TTSProvider:
    """
    Factory function to create a TTS provider based on config.

    Args:
        config: Top-level config dict containing a "tts" key.
                Expected shape:
                  {
                    "tts": {
                      "provider": "edge",
                      "voice": "de-DE-ConradNeural"
                    }
                  }

    Returns:
        A TTSProvider instance.

    Raises:
        ValueError: If the provider name is not recognised.
    """
    tts_config = config.get("tts", {})
    provider_name = tts_config.get("provider", "edge")

    if provider_name == "edge":
        voice = tts_config.get("voice", EdgeTTSProvider.DEFAULT_VOICE)
        return EdgeTTSProvider(voice=voice)

    raise ValueError(f"Unknown TTS provider: {provider_name!r}")


__all__ = [
    "TTSProvider",
    "EdgeTTSProvider",
    "create_tts_provider",
]
