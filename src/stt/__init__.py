"""STT provider package with factory function."""

from src.stt.base import STTProvider
from src.stt.groq import GroqSTTProvider


def create_stt_provider(config: dict) -> STTProvider:
    """
    Factory function to create an STT provider based on config.

    Args:
        config: Top-level config dict containing an "stt" key.
                Expected shape:
                  {
                    "stt": {
                      "provider": "groq",
                      "groq": { "api_key": "..." }
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

    raise ValueError(f"Unknown STT provider: {provider_name!r}")


__all__ = ["STTProvider", "GroqSTTProvider", "create_stt_provider"]
