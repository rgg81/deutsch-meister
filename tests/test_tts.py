"""Unit tests for the TTS provider abstraction."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tts import TTSProvider, EdgeTTSProvider, create_tts_provider
from src.tts.base import TTSProvider as TTSProviderBase


class TestTTSProviderInterface:
    """Tests for the TTSProvider abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            TTSProviderBase()

    def test_custom_implementation_works(self):
        class DummyProvider(TTSProvider):
            async def synthesize(self, text, output_path, voice=None):
                return output_path

        provider = DummyProvider()
        assert isinstance(provider, TTSProvider)


class TestEdgeTTSProvider:
    """Tests for the EdgeTTSProvider implementation."""

    def test_default_voice(self):
        provider = EdgeTTSProvider()
        assert provider.voice == "de-DE-ConradNeural"

    def test_custom_voice(self):
        provider = EdgeTTSProvider(voice="de-DE-KatjaNeural")
        assert provider.voice == "de-DE-KatjaNeural"

    @pytest.mark.asyncio
    async def test_synthesize_uses_default_voice_when_none_passed(self, tmp_path):
        output = str(tmp_path / "out.ogg")

        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock()

        with patch("src.tts.edge.edge_tts.Communicate", return_value=mock_communicate) as mock_cls, \
             patch("src.tts.edge.convert_to_ogg_opus", new_callable=AsyncMock, return_value=output):
            provider = EdgeTTSProvider(voice="de-DE-ConradNeural")
            result = await provider.synthesize("Hallo Welt", output)

        mock_cls.assert_called_once_with("Hallo Welt", "de-DE-ConradNeural")
        assert result == output

    @pytest.mark.asyncio
    async def test_synthesize_uses_voice_override(self, tmp_path):
        output = str(tmp_path / "out.ogg")

        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock()

        with patch("src.tts.edge.edge_tts.Communicate", return_value=mock_communicate) as mock_cls, \
             patch("src.tts.edge.convert_to_ogg_opus", new_callable=AsyncMock, return_value=output):
            provider = EdgeTTSProvider(voice="de-DE-ConradNeural")
            result = await provider.synthesize("Guten Tag", output, voice="de-DE-KatjaNeural")

        mock_cls.assert_called_once_with("Guten Tag", "de-DE-KatjaNeural")
        assert result == output

    @pytest.mark.asyncio
    async def test_synthesize_calls_convert_to_ogg(self, tmp_path):
        output = str(tmp_path / "out.ogg")
        expected_mp3 = output.replace(".ogg", ".mp3")

        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock()

        with patch("src.tts.edge.edge_tts.Communicate", return_value=mock_communicate), \
             patch("src.tts.edge.convert_to_ogg_opus", new_callable=AsyncMock, return_value=output) as mock_convert:
            provider = EdgeTTSProvider()
            await provider.synthesize("Test", output)

        mock_communicate.save.assert_called_once_with(expected_mp3)
        mock_convert.assert_called_once_with(expected_mp3, output)

    @pytest.mark.asyncio
    async def test_synthesize_cleans_up_tmp_mp3(self, tmp_path):
        output = str(tmp_path / "out.ogg")
        tmp_mp3 = output.replace(".ogg", ".mp3")

        # Create a fake MP3 file to verify cleanup
        open(tmp_mp3, "w").close()

        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock()

        with patch("src.tts.edge.edge_tts.Communicate", return_value=mock_communicate), \
             patch("src.tts.edge.convert_to_ogg_opus", new_callable=AsyncMock, return_value=output):
            provider = EdgeTTSProvider()
            await provider.synthesize("Test", output)

        from pathlib import Path
        assert not Path(tmp_mp3).exists()

    @pytest.mark.asyncio
    async def test_synthesize_cleans_up_mp3_on_error(self, tmp_path):
        output = str(tmp_path / "out.ogg")
        tmp_mp3 = output.replace(".ogg", ".mp3")

        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock(side_effect=RuntimeError("TTS error"))

        with patch("src.tts.edge.edge_tts.Communicate", return_value=mock_communicate):
            provider = EdgeTTSProvider()
            with pytest.raises(RuntimeError, match="TTS error"):
                await provider.synthesize("Test", output)

        from pathlib import Path
        assert not Path(tmp_mp3).exists()

    @pytest.mark.asyncio
    async def test_synthesize_raises_on_failure(self, tmp_path):
        output = str(tmp_path / "out.ogg")

        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock(side_effect=Exception("network error"))

        with patch("src.tts.edge.edge_tts.Communicate", return_value=mock_communicate):
            provider = EdgeTTSProvider()
            with pytest.raises(Exception, match="network error"):
                await provider.synthesize("Test", output)


class TestConvertToOggOpus:
    """Tests for the audio conversion helper."""

    @pytest.mark.asyncio
    async def test_returns_output_path_on_success(self, tmp_path):
        input_path = str(tmp_path / "input.mp3")
        output_path = str(tmp_path / "output.ogg")

        mock_proc = MagicMock()
        mock_proc.wait = AsyncMock(return_value=0)

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            from src.audio import convert_to_ogg_opus
            result = await convert_to_ogg_opus(input_path, output_path)

        assert result == output_path

    @pytest.mark.asyncio
    async def test_raises_on_nonzero_exit_code(self, tmp_path):
        input_path = str(tmp_path / "input.mp3")
        output_path = str(tmp_path / "output.ogg")

        mock_proc = MagicMock()
        mock_proc.wait = AsyncMock(return_value=1)

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            from src.audio import convert_to_ogg_opus
            with pytest.raises(RuntimeError, match="ffmpeg exited with code 1"):
                await convert_to_ogg_opus(input_path, output_path)

    @pytest.mark.asyncio
    async def test_ffmpeg_called_with_correct_args(self, tmp_path):
        input_path = str(tmp_path / "input.mp3")
        output_path = str(tmp_path / "output.ogg")

        mock_proc = MagicMock()
        mock_proc.wait = AsyncMock(return_value=0)

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc) as mock_exec:
            from src.audio import convert_to_ogg_opus
            await convert_to_ogg_opus(input_path, output_path)

        call_args = mock_exec.call_args[0]
        assert call_args[0] == "ffmpeg"
        assert "-y" in call_args
        assert "-i" in call_args
        assert input_path in call_args
        assert "-acodec" in call_args
        assert "libopus" in call_args
        assert output_path in call_args


class TestCreateTTSProvider:
    """Tests for the create_tts_provider factory function."""

    def test_creates_edge_provider_by_default(self):
        provider = create_tts_provider({})
        assert isinstance(provider, EdgeTTSProvider)
        assert provider.voice == EdgeTTSProvider.DEFAULT_VOICE

    def test_creates_edge_provider_explicitly(self):
        config = {"tts": {"provider": "edge"}}
        provider = create_tts_provider(config)
        assert isinstance(provider, EdgeTTSProvider)

    def test_custom_voice_is_applied(self):
        config = {"tts": {"provider": "edge", "voice": "de-DE-KatjaNeural"}}
        provider = create_tts_provider(config)
        assert isinstance(provider, EdgeTTSProvider)
        assert provider.voice == "de-DE-KatjaNeural"

    def test_default_voice_when_not_specified(self):
        config = {"tts": {"provider": "edge"}}
        provider = create_tts_provider(config)
        assert provider.voice == "de-DE-ConradNeural"

    def test_raises_for_unknown_provider(self):
        config = {"tts": {"provider": "unknown_provider"}}
        with pytest.raises(ValueError, match="Unknown TTS provider"):
            create_tts_provider(config)

    def test_missing_tts_section_uses_defaults(self):
        provider = create_tts_provider({"other": "config"})
        assert isinstance(provider, EdgeTTSProvider)
        assert provider.voice == EdgeTTSProvider.DEFAULT_VOICE
