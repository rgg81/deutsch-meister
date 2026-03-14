"""Unit tests for the SpeakTool."""

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.tools.speak import SpeakTool
from src.tts.base import TTSProvider


class MockTTSProvider(TTSProvider):
    """Minimal TTS provider for testing."""

    async def synthesize(self, text: str, output_path: str, voice: str | None = None) -> str:
        Path(output_path).write_bytes(b"fake ogg data")
        return output_path


def _cache_filename(text: str, voice: str | None = None) -> str:
    """Compute the expected cache filename for a given text and voice."""
    cache_key = f"{text}\x00{voice or ''}"
    return hashlib.md5(cache_key.encode()).hexdigest()[:12] + ".ogg"


class TestSpeakToolSchema:
    """Tests for tool schema / OpenAI function format."""

    def setup_method(self):
        self.tool = SpeakTool(MockTTSProvider())

    def test_name(self):
        assert self.tool.name == "speak"

    def test_description_mentions_german(self):
        assert "German" in self.tool.description

    def test_parameters_schema_type(self):
        assert self.tool.parameters["type"] == "object"

    def test_text_is_required(self):
        assert "text" in self.tool.parameters["required"]

    def test_voice_is_optional(self):
        schema = self.tool.parameters
        assert "voice" in schema["properties"]
        assert "voice" not in schema.get("required", [])

    def test_voice_description_does_not_hardcode_voice_id(self):
        description = self.tool.parameters["properties"]["voice"]["description"]
        assert "de-DE-ConradNeural" not in description
        assert "provider" in description.lower() or "configured" in description.lower()

    def test_to_schema_matches_openai_format(self):
        schema = self.tool.to_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "speak"
        assert "parameters" in schema["function"]


class TestSpeakToolExecute:
    """Tests for SpeakTool.execute()."""

    @pytest.mark.asyncio
    async def test_returns_ogg_file_path(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(side_effect=lambda t, p, voice=None: Path(p).write_bytes(b"x") or p)
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result = await tool.execute(text="Guten Morgen")

        assert result.endswith(".ogg")

    @pytest.mark.asyncio
    async def test_filename_is_content_hash(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(side_effect=lambda t, p, voice=None: Path(p).write_bytes(b"x") or p)
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result = await tool.execute(text="Hallo")

        assert Path(result).name == _cache_filename("Hallo")

    @pytest.mark.asyncio
    async def test_passes_voice_to_provider(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(side_effect=lambda t, p, voice=None: Path(p).write_bytes(b"x") or p)
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            await tool.execute(text="Tschüss", voice="de-DE-KatjaNeural")

        provider.synthesize.assert_called_once()
        assert provider.synthesize.call_args.kwargs["voice"] == "de-DE-KatjaNeural"

    @pytest.mark.asyncio
    async def test_no_voice_defaults_to_none(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(side_effect=lambda t, p, voice=None: Path(p).write_bytes(b"x") or p)
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            await tool.execute(text="Ja")

        assert provider.synthesize.call_args.kwargs["voice"] is None

    @pytest.mark.asyncio
    async def test_caches_by_content_hash(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(return_value="")
        tool = SpeakTool(provider)

        # Pre-create the cached file with content (non-empty = valid cache entry)
        cached = tmp_path / _cache_filename("Danke")
        cached.write_bytes(b"cached ogg data")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result = await tool.execute(text="Danke")

        # synthesize should NOT be called — file already exists and is non-empty
        provider.synthesize.assert_not_called()
        assert result == str(cached)

    @pytest.mark.asyncio
    async def test_empty_cached_file_triggers_re_synthesis(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(side_effect=lambda t, p, voice=None: Path(p).write_bytes(b"x") or p)
        tool = SpeakTool(provider)

        # Pre-create an empty file (partial/corrupt write)
        cached = tmp_path / _cache_filename("Brot")
        cached.touch()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            await tool.execute(text="Brot")

        # Empty file must not be treated as a cache hit
        provider.synthesize.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesize_called_when_file_missing(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(side_effect=lambda t, p, voice=None: Path(p).write_bytes(b"x") or p)
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            await tool.execute(text="Bitte")

        provider.synthesize.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_error_string_on_tts_failure(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(side_effect=RuntimeError("network error"))
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result = await tool.execute(text="Fehler")

        assert result.startswith("Error executing speak:")
        assert "network error" in result

    @pytest.mark.asyncio
    async def test_failed_synthesize_does_not_pollute_cache(self, tmp_path):
        """If synthesize raises, subsequent calls must not return a corrupt cached file."""
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(side_effect=RuntimeError("TTS down"))
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result1 = await tool.execute(text="Käse")
            # Subsequent call must also call synthesize, not return a cached corrupt file
            result2 = await tool.execute(text="Käse")

        assert result1.startswith("Error executing speak:")
        assert result2.startswith("Error executing speak:")
        assert provider.synthesize.call_count == 2

    @pytest.mark.asyncio
    async def test_same_text_always_produces_same_path(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(side_effect=lambda t, p, voice=None: Path(p).write_bytes(b"x") or p)
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result1 = await tool.execute(text="Morgen")
            result2 = await tool.execute(text="Morgen")

        assert result1 == result2

    @pytest.mark.asyncio
    async def test_different_texts_produce_different_paths(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(side_effect=lambda t, p, voice=None: Path(p).write_bytes(b"x") or p)
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result1 = await tool.execute(text="Hallo")
            result2 = await tool.execute(text="Tschüss")

        assert result1 != result2

    @pytest.mark.asyncio
    async def test_different_voices_produce_different_paths(self, tmp_path):
        """Same text with different voices must produce distinct cache entries."""
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(side_effect=lambda t, p, voice=None: Path(p).write_bytes(b"x") or p)
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result_male = await tool.execute(text="Hallo", voice="de-DE-ConradNeural")
            result_female = await tool.execute(text="Hallo", voice="de-DE-KatjaNeural")

        assert result_male != result_female
        assert provider.synthesize.call_count == 2
