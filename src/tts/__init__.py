"""TTS provider package with factory function."""

from src.tts.base import TTSProvider
from src.tts.edge import EdgeTTSProvider
from src.tts.fallback import FallbackTTSProvider
from src.tts.piper import PiperTTSProvider


def create_tts_provider(config: dict) -> TTSProvider:
    """
    Factory function to create a TTS provider based on config.

    Args:
        config: Top-level config dict containing a "tts" key.
                Supported shapes:

                  # Microsoft Edge TTS (cloud, neural quality)
                  {"tts": {"provider": "edge", "voice": "de-DE-ConradNeural"}}

                  # Local Piper TTS (offline, CPU)
                  {"tts": {"provider": "piper", "piper": {"model": "de_DE-thorsten-high"}}}

                  # Edge with Piper fallback (recommended)
                  {
                    "tts": {
                      "provider": "edge_with_fallback",
                      "voice": "de-DE-ConradNeural",
                      "piper": {"model": "de_DE-thorsten-high"}
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

    if provider_name == "piper":
        piper_cfg = tts_config.get("piper", {})
        model = piper_cfg.get("model", PiperTTSProvider.DEFAULT_MODEL)
        return PiperTTSProvider(model=model)

    if provider_name == "edge_with_fallback":
        voice = tts_config.get("voice", EdgeTTSProvider.DEFAULT_VOICE)
        piper_cfg = tts_config.get("piper", {})
        model = piper_cfg.get("model", PiperTTSProvider.DEFAULT_MODEL)
        return FallbackTTSProvider([
            EdgeTTSProvider(voice=voice),
            PiperTTSProvider(model=model),
        ])

    raise ValueError(f"Unknown TTS provider: {provider_name!r}")


__all__ = [
    "TTSProvider",
    "EdgeTTSProvider",
    "PiperTTSProvider",
    "FallbackTTSProvider",
    "create_tts_provider",
]
