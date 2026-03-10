"""Unit tests for the STT provider abstraction."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.stt import STTProvider, GroqSTTProvider, create_stt_provider
from src.stt.base import STTProvider as STTProviderBase


class TestSTTProviderInterface:
    """Tests for the STTProvider abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            STTProviderBase()

    def test_custom_implementation_works(self):
        class DummyProvider(STTProvider):
            async def transcribe(self, file_path):
                return "hello"

        provider = DummyProvider()
        assert isinstance(provider, STTProvider)


class TestGroqSTTProvider:
    """Tests for the GroqSTTProvider implementation."""

    def test_uses_env_var_when_no_key_passed(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "env-key")
        provider = GroqSTTProvider()
        assert provider.api_key == "env-key"

    def test_explicit_key_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "env-key")
        provider = GroqSTTProvider(api_key="explicit-key")
        assert provider.api_key == "explicit-key"

    def test_no_key_returns_empty_string(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        provider = GroqSTTProvider(api_key=None)
        assert provider.api_key is None

    @pytest.mark.asyncio
    async def test_transcribe_returns_empty_when_no_api_key(self, monkeypatch, tmp_path):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        provider = GroqSTTProvider(api_key=None)
        audio = tmp_path / "audio.ogg"
        audio.write_bytes(b"fake")
        result = await provider.transcribe(audio)
        assert result == ""

    @pytest.mark.asyncio
    async def test_transcribe_returns_empty_when_file_not_found(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        provider = GroqSTTProvider(api_key="test-key")
        result = await provider.transcribe("/nonexistent/file.ogg")
        assert result == ""

    @pytest.mark.asyncio
    async def test_transcribe_success(self, tmp_path):
        audio = tmp_path / "audio.ogg"
        audio.write_bytes(b"fake audio content")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"text": "Guten Morgen"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        provider = GroqSTTProvider(api_key="test-key")
        with patch("src.stt.groq.httpx.AsyncClient", return_value=mock_client):
            result = await provider.transcribe(audio)

        assert result == "Guten Morgen"
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer test-key"

    @pytest.mark.asyncio
    async def test_transcribe_handles_api_error(self, tmp_path):
        audio = tmp_path / "audio.ogg"
        audio.write_bytes(b"fake audio content")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("API error"))

        provider = GroqSTTProvider(api_key="test-key")
        with patch("src.stt.groq.httpx.AsyncClient", return_value=mock_client):
            result = await provider.transcribe(audio)

        assert result == ""

    @pytest.mark.asyncio
    async def test_transcribe_returns_empty_on_missing_text_key(self, tmp_path):
        audio = tmp_path / "audio.ogg"
        audio.write_bytes(b"fake audio content")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {}  # no "text" key

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        provider = GroqSTTProvider(api_key="test-key")
        with patch("src.stt.groq.httpx.AsyncClient", return_value=mock_client):
            result = await provider.transcribe(audio)

        assert result == ""


class TestCreateSTTProvider:
    """Tests for the create_stt_provider factory function."""

    def test_creates_groq_provider_by_default(self):
        config = {"stt": {"provider": "groq", "groq": {"api_key": "key123"}}}
        provider = create_stt_provider(config)
        assert isinstance(provider, GroqSTTProvider)
        assert provider.api_key == "key123"

    def test_creates_groq_provider_when_no_stt_section(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "env-key")
        provider = create_stt_provider({})
        assert isinstance(provider, GroqSTTProvider)

    def test_groq_api_key_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "from-env")
        config = {"stt": {"provider": "groq", "groq": {}}}
        provider = create_stt_provider(config)
        assert isinstance(provider, GroqSTTProvider)
        assert provider.api_key == "from-env"

    def test_raises_for_unknown_provider(self):
        config = {"stt": {"provider": "unknown_provider"}}
        with pytest.raises(ValueError, match="Unknown STT provider"):
            create_stt_provider(config)

    def test_groq_provider_has_correct_api_url(self):
        config = {"stt": {"provider": "groq", "groq": {"api_key": "k"}}}
        provider = create_stt_provider(config)
        assert "groq.com" in provider.api_url
