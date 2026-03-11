"""STT provider package with factory function."""

from src.stt.base import STTProvider
from src.stt.fallback import FallbackSTTProvider
from src.stt.groq import GroqSTTProvider
from src.stt.whisper import WhisperSTTProvider


def create_stt_provider(config: dict) -> STTProvider:
    """
    Factory function to create an STT provider based on config.

    Args:
        config: Top-level config dict containing an "stt" key.
                Expected shape:
                  {
                    "stt": {
                      "provider": "groq" | "whisper" | "groq_with_fallback",
                      "groq": { "api_key": "..." },
                      "whisper": { "model": "base" }
                    }
                  }
                The "groq" api_key falls back to the GROQ_API_KEY environment variable.

    Returns:
        An STTProvider instance.

    Raises:
        ValueError: If the provider name is not recognised.
    """
    stt_config = config.get("stt", {})
    provider_name = stt_config.get("provider", "groq")

    if provider_name == "groq":
        groq_config = stt_config.get("groq", {})
        api_key = groq_config.get("api_key") or None
        return GroqSTTProvider(api_key=api_key)

    if provider_name == "whisper":
        whisper_config = stt_config.get("whisper", {})
        model_size = whisper_config.get("model", "base")
        return WhisperSTTProvider(model_size=model_size)

    if provider_name == "groq_with_fallback":
        groq_config = stt_config.get("groq", {})
        api_key = groq_config.get("api_key") or None
        whisper_config = stt_config.get("whisper", {})
        model_size = whisper_config.get("model", "base")
        return FallbackSTTProvider(
            providers=[
                GroqSTTProvider(api_key=api_key),
                WhisperSTTProvider(model_size=model_size),
            ]
        )

    raise ValueError(f"Unknown STT provider: {provider_name!r}")


__all__ = [
    "STTProvider",
    "GroqSTTProvider",
    "WhisperSTTProvider",
    "FallbackSTTProvider",
    "create_stt_provider",
]
