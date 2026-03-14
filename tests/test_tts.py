"""Unit tests for the TTS provider abstraction."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tts import TTSProvider, EdgeTTSProvider, FallbackTTSProvider, PiperTTSProvider, create_tts_provider
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
    async def test_synthesize_creates_parent_directory(self, tmp_path):
        output = str(tmp_path / "new_subdir" / "out.ogg")

        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock()

        with patch("src.tts.edge.edge_tts.Communicate", return_value=mock_communicate), \
             patch("src.tts.edge.convert_to_ogg_opus", new_callable=AsyncMock, return_value=output):
            provider = EdgeTTSProvider()
            result = await provider.synthesize("Test", output)

        from pathlib import Path
        assert Path(output).parent.exists()
        assert result == output

    @pytest.mark.asyncio
    async def test_synthesize_calls_convert_to_ogg(self, tmp_path):
        output = str(tmp_path / "out.ogg")
        expected_mp3 = str(Path(output).with_suffix(".mp3"))

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
        tmp_mp3 = str(Path(output).with_suffix(".mp3"))

        # Create a fake MP3 file to verify cleanup
        open(tmp_mp3, "w").close()

        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock()

        with patch("src.tts.edge.edge_tts.Communicate", return_value=mock_communicate), \
             patch("src.tts.edge.convert_to_ogg_opus", new_callable=AsyncMock, return_value=output):
            provider = EdgeTTSProvider()
            await provider.synthesize("Test", output)

        assert not Path(tmp_mp3).exists()

    @pytest.mark.asyncio
    async def test_synthesize_cleans_up_mp3_on_error(self, tmp_path):
        output = str(tmp_path / "out.ogg")
        tmp_mp3 = str(Path(output).with_suffix(".mp3"))

        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock(side_effect=RuntimeError("TTS error"))

        with patch("src.tts.edge.edge_tts.Communicate", return_value=mock_communicate):
            provider = EdgeTTSProvider()
            with pytest.raises(RuntimeError, match="TTS error"):
                await provider.synthesize("Test", output)

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
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(None, b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            from src.audio import convert_to_ogg_opus
            result = await convert_to_ogg_opus(input_path, output_path)

        assert result == output_path

    @pytest.mark.asyncio
    async def test_raises_on_nonzero_exit_code(self, tmp_path):
        input_path = str(tmp_path / "input.mp3")
        output_path = str(tmp_path / "output.ogg")

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(None, b"some ffmpeg error"))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            from src.audio import convert_to_ogg_opus
            with pytest.raises(RuntimeError, match="ffmpeg exited with code 1"):
                await convert_to_ogg_opus(input_path, output_path)

    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_ffmpeg_missing(self, tmp_path):
        input_path = str(tmp_path / "input.mp3")
        output_path = str(tmp_path / "output.ogg")

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            from src.audio import convert_to_ogg_opus
            with pytest.raises(RuntimeError, match="ffmpeg not found"):
                await convert_to_ogg_opus(input_path, output_path)

    @pytest.mark.asyncio
    async def test_ffmpeg_called_with_correct_args(self, tmp_path):
        input_path = str(tmp_path / "input.mp3")
        output_path = str(tmp_path / "output.ogg")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(None, b""))

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


class TestPiperTTSProvider:
    """Tests for the PiperTTSProvider implementation."""

    def test_default_model(self):
        provider = PiperTTSProvider()
        assert provider.model == "de_DE-thorsten-high"

    def test_custom_model(self):
        provider = PiperTTSProvider(model="de_DE-thorsten-low")
        assert provider.model == "de_DE-thorsten-low"

    @pytest.mark.asyncio
    async def test_synthesize_success(self, tmp_path):
        output = str(tmp_path / "out.ogg")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(None, b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc), \
             patch("src.tts.piper.convert_to_ogg_opus", new_callable=AsyncMock, return_value=output):
            provider = PiperTTSProvider()
            result = await provider.synthesize("Hallo Welt", output)

        assert result == output

    @pytest.mark.asyncio
    async def test_synthesize_passes_text_via_stdin(self, tmp_path):
        output = str(tmp_path / "out.ogg")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(None, b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc) as mock_exec, \
             patch("src.tts.piper.convert_to_ogg_opus", new_callable=AsyncMock, return_value=output):
            provider = PiperTTSProvider()
            await provider.synthesize("Guten Tag", output)

        mock_proc.communicate.assert_called_once_with(input=b"Guten Tag")

    @pytest.mark.asyncio
    async def test_synthesize_creates_parent_directory(self, tmp_path):
        output = str(tmp_path / "new_subdir" / "out.ogg")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(None, b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc), \
             patch("src.tts.piper.convert_to_ogg_opus", new_callable=AsyncMock, return_value=output):
            provider = PiperTTSProvider()
            await provider.synthesize("Test", output)

        assert Path(output).parent.exists()

    @pytest.mark.asyncio
    async def test_synthesize_cleans_up_wav_on_success(self, tmp_path):
        output = str(tmp_path / "out.ogg")
        tmp_wav = str(Path(output).with_suffix(".wav"))
        open(tmp_wav, "w").close()

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(None, b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc), \
             patch("src.tts.piper.convert_to_ogg_opus", new_callable=AsyncMock, return_value=output):
            provider = PiperTTSProvider()
            await provider.synthesize("Test", output)

        assert not Path(tmp_wav).exists()

    @pytest.mark.asyncio
    async def test_synthesize_cleans_up_wav_on_error(self, tmp_path):
        output = str(tmp_path / "out.ogg")
        tmp_wav = str(Path(output).with_suffix(".wav"))
        open(tmp_wav, "w").close()

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(None, b"model not found"))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            provider = PiperTTSProvider()
            with pytest.raises(RuntimeError, match="piper exited with code 1"):
                await provider.synthesize("Test", output)

        assert not Path(tmp_wav).exists()

    @pytest.mark.asyncio
    async def test_synthesize_raises_runtime_error_when_piper_missing(self, tmp_path):
        output = str(tmp_path / "out.ogg")

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            provider = PiperTTSProvider()
            with pytest.raises(RuntimeError, match="piper not found"):
                await provider.synthesize("Test", output)

    @pytest.mark.asyncio
    async def test_synthesize_uses_correct_model(self, tmp_path):
        output = str(tmp_path / "out.ogg")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(None, b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc) as mock_exec, \
             patch("src.tts.piper.convert_to_ogg_opus", new_callable=AsyncMock, return_value=output):
            provider = PiperTTSProvider(model="de_DE-thorsten-low")
            await provider.synthesize("Test", output)

        call_args = mock_exec.call_args[0]
        assert "piper" in call_args
        assert "de_DE-thorsten-low" in call_args


class TestFallbackTTSProvider:
    """Tests for the FallbackTTSProvider implementation."""

    def test_requires_at_least_one_provider(self):
        with pytest.raises(ValueError, match="at least one provider"):
            FallbackTTSProvider([])

    @pytest.mark.asyncio
    async def test_returns_first_provider_result_when_it_succeeds(self, tmp_path):
        output = str(tmp_path / "out.ogg")
        primary = AsyncMock(spec=TTSProvider)
        primary.synthesize = AsyncMock(return_value=output)
        fallback = AsyncMock(spec=TTSProvider)

        provider = FallbackTTSProvider([primary, fallback])
        result = await provider.synthesize("Hallo", output)

        assert result == output
        primary.synthesize.assert_called_once_with("Hallo", output, None)
        fallback.synthesize.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_when_primary_fails(self, tmp_path):
        output = str(tmp_path / "out.ogg")
        primary = AsyncMock(spec=TTSProvider)
        primary.synthesize = AsyncMock(side_effect=RuntimeError("network error"))
        fallback = AsyncMock(spec=TTSProvider)
        fallback.synthesize = AsyncMock(return_value=output)

        provider = FallbackTTSProvider([primary, fallback])
        result = await provider.synthesize("Hallo", output)

        assert result == output
        primary.synthesize.assert_called_once()
        fallback.synthesize.assert_called_once_with("Hallo", output, None)

    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_all_fail(self, tmp_path):
        output = str(tmp_path / "out.ogg")
        p1 = AsyncMock(spec=TTSProvider)
        p1.synthesize = AsyncMock(side_effect=RuntimeError("error1"))
        p2 = AsyncMock(spec=TTSProvider)
        p2.synthesize = AsyncMock(side_effect=RuntimeError("error2"))

        provider = FallbackTTSProvider([p1, p2])
        with pytest.raises(RuntimeError, match="All TTS providers failed"):
            await provider.synthesize("Hallo", output)

    @pytest.mark.asyncio
    async def test_passes_voice_override_to_providers(self, tmp_path):
        output = str(tmp_path / "out.ogg")
        primary = AsyncMock(spec=TTSProvider)
        primary.synthesize = AsyncMock(return_value=output)

        provider = FallbackTTSProvider([primary])
        await provider.synthesize("Hallo", output, voice="de-DE-KatjaNeural")

        primary.synthesize.assert_called_once_with("Hallo", output, "de-DE-KatjaNeural")

    @pytest.mark.asyncio
    async def test_tries_all_providers_before_giving_up(self, tmp_path):
        output = str(tmp_path / "out.ogg")
        providers = [AsyncMock(spec=TTSProvider) for _ in range(3)]
        for p in providers:
            p.synthesize = AsyncMock(side_effect=RuntimeError("fail"))

        provider = FallbackTTSProvider(providers)
        with pytest.raises(RuntimeError, match="All TTS providers failed"):
            await provider.synthesize("Hallo", output)

        for p in providers:
            p.synthesize.assert_called_once()


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

    def test_creates_piper_provider(self):
        config = {"tts": {"provider": "piper"}}
        provider = create_tts_provider(config)
        assert isinstance(provider, PiperTTSProvider)
        assert provider.model == PiperTTSProvider.DEFAULT_MODEL

    def test_creates_piper_provider_with_custom_model(self):
        config = {"tts": {"provider": "piper", "piper": {"model": "de_DE-thorsten-low"}}}
        provider = create_tts_provider(config)
        assert isinstance(provider, PiperTTSProvider)
        assert provider.model == "de_DE-thorsten-low"

    def test_creates_edge_with_fallback_provider(self):
        config = {"tts": {"provider": "edge_with_fallback", "voice": "de-DE-ConradNeural"}}
        provider = create_tts_provider(config)
        assert isinstance(provider, FallbackTTSProvider)
        assert len(provider.providers) == 2
        assert isinstance(provider.providers[0], EdgeTTSProvider)
        assert isinstance(provider.providers[1], PiperTTSProvider)

    def test_edge_with_fallback_applies_voice(self):
        config = {"tts": {"provider": "edge_with_fallback", "voice": "de-DE-KatjaNeural"}}
        provider = create_tts_provider(config)
        assert isinstance(provider, FallbackTTSProvider)
        assert provider.providers[0].voice == "de-DE-KatjaNeural"

    def test_edge_with_fallback_applies_piper_model(self):
        config = {
            "tts": {
                "provider": "edge_with_fallback",
                "piper": {"model": "de_DE-thorsten-low"},
            }
        }
        provider = create_tts_provider(config)
        assert isinstance(provider, FallbackTTSProvider)
        assert provider.providers[1].model == "de_DE-thorsten-low"
