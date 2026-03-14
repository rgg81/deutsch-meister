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
        Path(output_path).touch()
        return output_path


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
        provider.synthesize = AsyncMock(return_value=str(tmp_path / "out.ogg"))
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result = await tool.execute(text="Guten Morgen")

        assert result.endswith(".ogg")

    @pytest.mark.asyncio
    async def test_filename_is_content_hash(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(return_value="")
        tool = SpeakTool(provider)

        expected_hash = hashlib.md5("Hallo".encode()).hexdigest()[:12]

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result = await tool.execute(text="Hallo")

        assert Path(result).name == f"{expected_hash}.ogg"

    @pytest.mark.asyncio
    async def test_passes_voice_to_provider(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(return_value="")
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            await tool.execute(text="Tschüss", voice="de-DE-KatjaNeural")

        provider.synthesize.assert_called_once()
        assert provider.synthesize.call_args.kwargs["voice"] == "de-DE-KatjaNeural"

    @pytest.mark.asyncio
    async def test_no_voice_defaults_to_none(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(return_value="")
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

        # Pre-create the cached file
        filename = hashlib.md5("Danke".encode()).hexdigest()[:12] + ".ogg"
        cached = tmp_path / filename
        cached.touch()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result = await tool.execute(text="Danke")

        # synthesize should NOT be called — file already exists
        provider.synthesize.assert_not_called()
        assert result == str(cached)

    @pytest.mark.asyncio
    async def test_synthesize_called_when_file_missing(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(return_value="")
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
    async def test_same_text_always_produces_same_path(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(return_value="")
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result1 = await tool.execute(text="Morgen")
            result2 = await tool.execute(text="Morgen")

        assert result1 == result2

    @pytest.mark.asyncio
    async def test_different_texts_produce_different_paths(self, tmp_path):
        provider = AsyncMock(spec=TTSProvider)
        provider.synthesize = AsyncMock(return_value="")
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result1 = await tool.execute(text="Hallo")
            result2 = await tool.execute(text="Tschüss")

        assert result1 != result2
