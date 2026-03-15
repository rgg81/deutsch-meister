"""
End-to-end integration tests for the audio round-trip pipeline.

Tests the full pipeline: voice message → STT transcription → agent processes
→ speak tool → OGG file → message with media.

All external I/O is mocked; no real Telegram connection or network calls are made.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanobot.bus.events import OutboundMessage
from nanobot.channels.telegram import TelegramChannel

from src.stt import (
    FallbackSTTProvider,
    GroqSTTProvider,
    WhisperSTTProvider,
    create_stt_provider,
)
from src.tts import (
    EdgeTTSProvider,
    FallbackTTSProvider,
    PiperTTSProvider,
    create_tts_provider,
)
from src.tools.speak import SpeakTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_groq_client_mock(text: str) -> MagicMock:
    """Return an AsyncMock httpx.AsyncClient whose .post() returns *text*."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"text": text}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client


def _make_groq_client_mock_error() -> MagicMock:
    """Return an AsyncMock httpx.AsyncClient whose .post() raises an exception."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=Exception("Groq API unavailable"))
    return mock_client


# ---------------------------------------------------------------------------
# STT: voice message → transcription
# ---------------------------------------------------------------------------


class TestSTTTranscribesVoiceMessage:
    """Voice message → STT → text (Groq provider)."""

    @pytest.mark.asyncio
    async def test_groq_transcribes_voice_message(self, tmp_path):
        """Groq STT provider successfully transcribes a voice OGG file."""
        audio = tmp_path / "voice.ogg"
        audio.write_bytes(b"fake ogg data")

        provider = GroqSTTProvider(api_key="test-key")
        with patch("src.stt.groq.httpx.AsyncClient", return_value=_make_groq_client_mock("Guten Morgen")):
            result = await provider.transcribe(str(audio))

        assert result == "Guten Morgen"

    @pytest.mark.asyncio
    async def test_transcription_reaches_pipeline(self, tmp_path):
        """Transcribed text from STT can be passed downstream."""
        audio = tmp_path / "voice.ogg"
        audio.write_bytes(b"fake ogg data")

        provider = create_stt_provider({
            "stt": {"provider": "groq", "groq": {"api_key": "test-key"}}
        })
        with patch("src.stt.groq.httpx.AsyncClient", return_value=_make_groq_client_mock("Wie geht es Ihnen?")):
            transcription = await provider.transcribe(str(audio))

        assert transcription == "Wie geht es Ihnen?"
        assert len(transcription) > 0

    @pytest.mark.asyncio
    async def test_empty_transcription_on_invalid_audio(self, tmp_path):
        """Invalid / corrupted audio file → Groq returns empty string, not an exception."""
        audio = tmp_path / "corrupt.ogg"
        audio.write_bytes(b"\x00\x00\x00")  # invalid audio

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"text": ""}  # Groq returns empty for invalid audio

        mock_client = _make_groq_client_mock("")
        mock_client.post = AsyncMock(return_value=mock_response)

        provider = GroqSTTProvider(api_key="test-key")
        with patch("src.stt.groq.httpx.AsyncClient", return_value=mock_client):
            result = await provider.transcribe(str(audio))

        assert result == ""


class TestSTTFallbackOnGroqFailure:
    """Groq fails → faster-whisper takes over."""

    @pytest.mark.asyncio
    async def test_falls_back_to_whisper_when_groq_fails(self, tmp_path):
        """Groq raises → FallbackSTTProvider calls Whisper and returns its result."""
        audio = tmp_path / "voice.ogg"
        audio.write_bytes(b"fake ogg data")

        groq_provider = GroqSTTProvider(api_key="test-key")
        whisper_provider = WhisperSTTProvider(model_size="tiny")

        # Groq will fail; Whisper will succeed
        mock_segment = MagicMock()
        mock_segment.text = "Auf Wiedersehen"
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], MagicMock())

        with patch("src.stt.groq.httpx.AsyncClient", return_value=_make_groq_client_mock_error()), \
             patch.object(whisper_provider, "_load_model", return_value=mock_model):
            provider = FallbackSTTProvider(providers=[groq_provider, whisper_provider])
            result = await provider.transcribe(str(audio))

        assert result == "Auf Wiedersehen"

    @pytest.mark.asyncio
    async def test_falls_back_to_whisper_when_groq_returns_empty(self, tmp_path):
        """Groq returns empty string → FallbackSTTProvider tries Whisper."""
        audio = tmp_path / "voice.ogg"
        audio.write_bytes(b"fake ogg data")

        groq_provider = GroqSTTProvider(api_key="test-key")
        whisper_provider = WhisperSTTProvider(model_size="tiny")

        mock_segment = MagicMock()
        mock_segment.text = "Guten Tag"
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], MagicMock())

        with patch("src.stt.groq.httpx.AsyncClient", return_value=_make_groq_client_mock("")), \
             patch.object(whisper_provider, "_load_model", return_value=mock_model):
            provider = FallbackSTTProvider(providers=[groq_provider, whisper_provider])
            result = await provider.transcribe(str(audio))

        assert result == "Guten Tag"

    @pytest.mark.asyncio
    async def test_factory_creates_fallback_chain_for_groq_with_fallback(self, tmp_path):
        """create_stt_provider with 'groq_with_fallback' builds the correct provider chain."""
        provider = create_stt_provider({
            "stt": {
                "provider": "groq_with_fallback",
                "groq": {"api_key": "test-key"},
                "whisper": {"model": "tiny"},
            }
        })

        assert isinstance(provider, FallbackSTTProvider)
        assert len(provider.providers) == 2
        assert isinstance(provider.providers[0], GroqSTTProvider)
        assert isinstance(provider.providers[1], WhisperSTTProvider)

    @pytest.mark.asyncio
    async def test_returns_empty_when_all_stt_providers_fail(self, tmp_path):
        """All STT providers fail → pipeline receives empty string gracefully."""
        audio = tmp_path / "voice.ogg"
        audio.write_bytes(b"fake ogg data")

        groq = AsyncMock(spec=GroqSTTProvider)
        groq.transcribe = AsyncMock(side_effect=Exception("network error"))
        whisper = AsyncMock(spec=WhisperSTTProvider)
        whisper.transcribe = AsyncMock(return_value="")

        provider = FallbackSTTProvider(providers=[groq, whisper])
        result = await provider.transcribe(str(audio))

        assert result == ""


# ---------------------------------------------------------------------------
# TTS: text → OGG file
# ---------------------------------------------------------------------------


class TestTTSGeneratesOgg:
    """Text → TTS → OGG file."""

    @pytest.mark.asyncio
    async def test_edge_tts_generates_ogg(self, tmp_path):
        """EdgeTTSProvider produces an OGG output file path."""
        output = str(tmp_path / "out.ogg")

        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock()

        with patch("src.tts.edge.edge_tts.Communicate", return_value=mock_communicate), \
             patch("src.tts.edge.convert_to_ogg_opus", new_callable=AsyncMock, return_value=output):
            provider = EdgeTTSProvider(voice="de-DE-ConradNeural")
            result = await provider.synthesize("Schmetterling", output)

        assert result.endswith(".ogg")
        assert result == output

    @pytest.mark.asyncio
    async def test_speak_tool_returns_ogg_path(self, tmp_path):
        """SpeakTool.execute() returns a path ending in .ogg."""
        provider = AsyncMock()
        provider.synthesize = AsyncMock(
            side_effect=lambda t, p, voice=None: Path(p).write_bytes(b"fake ogg") or p
        )
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result = await tool.execute(text="Hallo")

        assert result.endswith(".ogg")

    @pytest.mark.asyncio
    async def test_speak_tool_error_reported_to_user(self, tmp_path):
        """TTS generation failure produces a descriptive error string, not a crash."""
        provider = AsyncMock()
        provider.synthesize = AsyncMock(side_effect=RuntimeError("TTS service down"))
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result = await tool.execute(text="Eichhörnchen")

        assert result.startswith("Error executing speak:")
        assert "TTS service down" in result


class TestTTSFallbackOnEdgeFailure:
    """edge-tts fails → Piper takes over."""

    @pytest.mark.asyncio
    async def test_falls_back_to_piper_when_edge_raises(self, tmp_path):
        """EdgeTTSProvider raises → FallbackTTSProvider calls Piper and returns its result."""
        output = str(tmp_path / "out.ogg")

        edge = AsyncMock(spec=EdgeTTSProvider)
        edge.synthesize = AsyncMock(side_effect=RuntimeError("NoAudioReceived"))
        piper = AsyncMock(spec=PiperTTSProvider)
        piper.synthesize = AsyncMock(return_value=output)

        provider = FallbackTTSProvider([edge, piper])
        result = await provider.synthesize("Schmetterling", output)

        assert result == output
        edge.synthesize.assert_called_once()
        piper.synthesize.assert_called_once()

    @pytest.mark.asyncio
    async def test_factory_creates_fallback_chain_for_edge_with_fallback(self):
        """create_tts_provider with 'edge_with_fallback' builds the correct provider chain."""
        provider = create_tts_provider({
            "tts": {
                "provider": "edge_with_fallback",
                "voice": "de-DE-ConradNeural",
                "piper": {"model": "de_DE-thorsten-high"},
            }
        })

        assert isinstance(provider, FallbackTTSProvider)
        assert len(provider.providers) == 2
        assert isinstance(provider.providers[0], EdgeTTSProvider)
        assert isinstance(provider.providers[1], PiperTTSProvider)

    @pytest.mark.asyncio
    async def test_raises_when_all_tts_providers_fail(self, tmp_path):
        """All TTS providers fail → RuntimeError is raised (SpeakTool catches and returns error string)."""
        output = str(tmp_path / "out.ogg")

        p1 = AsyncMock(spec=EdgeTTSProvider)
        p1.synthesize = AsyncMock(side_effect=RuntimeError("edge failed"))
        p2 = AsyncMock(spec=PiperTTSProvider)
        p2.synthesize = AsyncMock(side_effect=RuntimeError("piper failed"))

        provider = FallbackTTSProvider([p1, p2])
        with pytest.raises(RuntimeError, match="All TTS providers failed"):
            await provider.synthesize("Schmetterling", output)

    @pytest.mark.asyncio
    async def test_speak_tool_handles_all_tts_failure_gracefully(self, tmp_path):
        """SpeakTool catches RuntimeError from all-failed TTS and returns an error string."""
        p1 = AsyncMock(spec=EdgeTTSProvider)
        p1.synthesize = AsyncMock(side_effect=RuntimeError("edge failed"))
        p2 = AsyncMock(spec=PiperTTSProvider)
        p2.synthesize = AsyncMock(side_effect=RuntimeError("piper failed"))

        fallback_provider = FallbackTTSProvider([p1, p2])
        tool = SpeakTool(fallback_provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result = await tool.execute(text="Eichhörnchen")

        assert result.startswith("Error executing speak:")


# ---------------------------------------------------------------------------
# Full round-trip: voice in → transcription → speak tool → voice out
# ---------------------------------------------------------------------------


class TestFullRoundTrip:
    """Voice message → STT → agent calls speak → OGG file returned."""

    @pytest.mark.asyncio
    async def test_voice_in_text_out_via_stt(self, tmp_path):
        """
        Step 1 of the pipeline: inbound voice OGG → STT → transcription text.

        The transcription text is what the agent receives as the user's message.
        """
        voice_file = tmp_path / "inbound.ogg"
        voice_file.write_bytes(b"fake ogg data")

        stt = create_stt_provider({
            "stt": {"provider": "groq", "groq": {"api_key": "test-key"}}
        })
        with patch("src.stt.groq.httpx.AsyncClient", return_value=_make_groq_client_mock("Wie sagt man butterfly auf Deutsch?")):
            transcription = await stt.transcribe(str(voice_file))

        assert transcription == "Wie sagt man butterfly auf Deutsch?"

    @pytest.mark.asyncio
    async def test_speak_tool_produces_ogg_for_agent_response(self, tmp_path):
        """
        Step 2 of the pipeline: agent calls speak tool → OGG file path returned.

        The agent includes this path in the outbound message media array.
        """
        tts_provider = AsyncMock()
        tts_provider.synthesize = AsyncMock(
            side_effect=lambda text, path, voice=None: Path(path).write_bytes(b"fake ogg") or path
        )
        tool = SpeakTool(tts_provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            ogg_path = await tool.execute(text="Schmetterling")

        assert ogg_path.endswith(".ogg")
        assert Path(ogg_path).exists()
        assert Path(ogg_path).stat().st_size > 0

    @pytest.mark.asyncio
    async def test_complete_voice_round_trip(self, tmp_path):
        """
        Full pipeline: inbound voice → STT → speak tool → OutboundMessage → send_voice.

        Simulates the agent receiving a transcribed voice query, responding with a
        synthesized audio message, and sending it via Telegram (send_voice is called
        for .ogg media).
        """
        # --- Step 1: Inbound voice message → transcription ---
        inbound_ogg = tmp_path / "inbound.ogg"
        inbound_ogg.write_bytes(b"fake inbound ogg")

        stt = create_stt_provider({
            "stt": {"provider": "groq", "groq": {"api_key": "test-key"}}
        })
        with patch(
            "src.stt.groq.httpx.AsyncClient",
            return_value=_make_groq_client_mock("Wie sagt man Schmetterling?"),
        ):
            transcription = await stt.transcribe(str(inbound_ogg))

        assert transcription == "Wie sagt man Schmetterling?"

        # --- Step 2: Agent processes query and calls speak tool ---
        tts_provider = AsyncMock()
        tts_provider.synthesize = AsyncMock(
            side_effect=lambda text, path, voice=None: Path(path).write_bytes(b"fake ogg") or path
        )
        speak_tool = SpeakTool(tts_provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            outbound_ogg = await speak_tool.execute(text="Schmetterling")

        assert outbound_ogg.endswith(".ogg")
        assert Path(outbound_ogg).exists()
        assert Path(outbound_ogg).stat().st_size > 0

        # --- Step 3: OutboundMessage with OGG media triggers send_voice on Telegram ---
        msg = OutboundMessage(
            channel="telegram",
            chat_id="123456",
            content="Schmetterling bedeutet butterfly.",
            media=[outbound_ogg],
        )

        # OGG extension must map to "voice" media type
        assert TelegramChannel._get_media_type(outbound_ogg) == "voice"

        # Build a minimal TelegramChannel with a mocked bot and call send()
        channel = TelegramChannel.__new__(TelegramChannel)
        mock_bot = AsyncMock()
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        channel._app = mock_app
        channel._message_threads = {}
        channel.config = MagicMock()
        channel.config.reply_to_message = False
        channel._stop_typing = MagicMock()

        await channel.send(msg)

        mock_bot.send_voice.assert_called_once()

    @pytest.mark.asyncio
    async def test_round_trip_with_stt_fallback(self, tmp_path):
        """
        Full pipeline with STT fallback: Groq fails → Whisper transcribes
        → speak tool produces OGG response.
        """
        inbound_ogg = tmp_path / "inbound.ogg"
        inbound_ogg.write_bytes(b"fake inbound ogg")

        # STT: Groq fails, Whisper succeeds
        groq = GroqSTTProvider(api_key="test-key")
        whisper = WhisperSTTProvider(model_size="tiny")

        mock_segment = MagicMock()
        mock_segment.text = "Guten Morgen"
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], MagicMock())

        stt = FallbackSTTProvider(providers=[groq, whisper])
        with patch("src.stt.groq.httpx.AsyncClient", return_value=_make_groq_client_mock_error()), \
             patch.object(whisper, "_load_model", return_value=mock_model):
            transcription = await stt.transcribe(str(inbound_ogg))

        assert transcription == "Guten Morgen"

        # TTS: speak tool produces OGG
        tts_provider = AsyncMock()
        tts_provider.synthesize = AsyncMock(
            side_effect=lambda text, path, voice=None: Path(path).write_bytes(b"fake ogg") or path
        )
        speak_tool = SpeakTool(tts_provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            outbound_ogg = await speak_tool.execute(text=transcription)

        assert outbound_ogg.endswith(".ogg")

    @pytest.mark.asyncio
    async def test_round_trip_with_tts_fallback(self, tmp_path):
        """
        Full pipeline with TTS fallback: edge-tts fails → Piper synthesizes
        → OGG response produced.
        """
        inbound_ogg = tmp_path / "inbound.ogg"
        inbound_ogg.write_bytes(b"fake inbound ogg")

        # STT: Groq succeeds
        stt = GroqSTTProvider(api_key="test-key")
        with patch("src.stt.groq.httpx.AsyncClient", return_value=_make_groq_client_mock("Hallo")):
            transcription = await stt.transcribe(str(inbound_ogg))

        assert transcription == "Hallo"

        # TTS: Edge fails, Piper succeeds (writes real bytes to the provided path)
        edge = AsyncMock(spec=EdgeTTSProvider)
        edge.synthesize = AsyncMock(side_effect=RuntimeError("NoAudioReceived"))
        piper = AsyncMock(spec=PiperTTSProvider)

        async def _piper_synthesize(text, path, voice=None):
            Path(path).write_bytes(b"fake piper ogg")
            return path

        piper.synthesize = AsyncMock(side_effect=_piper_synthesize)

        tts = FallbackTTSProvider([edge, piper])
        speak_tool = SpeakTool(tts)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            outbound_ogg = await speak_tool.execute(text=transcription)

        assert outbound_ogg.endswith(".ogg")
        assert Path(outbound_ogg).exists()
        assert Path(outbound_ogg).stat().st_size > 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases in the audio pipeline."""

    @pytest.mark.asyncio
    async def test_empty_transcription_does_not_crash_speak_tool(self, tmp_path):
        """Empty STT result → speak tool called with empty string → returns error string."""
        provider = AsyncMock()
        provider.synthesize = AsyncMock(side_effect=RuntimeError("empty text"))
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result = await tool.execute(text="")

        # SpeakTool must not raise; it must return an error string
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_nonexistent_audio_file_returns_empty_transcription(self):
        """Sending a path to a non-existent file → STT returns empty string."""
        provider = GroqSTTProvider(api_key="test-key")
        result = await provider.transcribe("/nonexistent/voice.ogg")
        assert result == ""

    @pytest.mark.asyncio
    async def test_zero_byte_audio_file_returns_empty_transcription(self, tmp_path):
        """Empty (0-byte) audio file → Groq returns empty transcription."""
        empty_ogg = tmp_path / "empty.ogg"
        empty_ogg.touch()  # 0 bytes

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"text": ""}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        provider = GroqSTTProvider(api_key="test-key")
        with patch("src.stt.groq.httpx.AsyncClient", return_value=mock_client):
            result = await provider.transcribe(str(empty_ogg))

        assert result == ""

    @pytest.mark.asyncio
    async def test_zero_byte_tts_output_is_not_cached(self, tmp_path):
        """
        A 0-byte output file (e.g. partial write) is treated as a cache miss.
        A subsequent call must re-synthesize rather than serve the empty file.
        """
        provider = AsyncMock()
        call_count = 0

        async def synthesize_side_effect(text, path, voice=None):
            nonlocal call_count
            call_count += 1
            Path(path).write_bytes(b"real ogg data")
            return path

        provider.synthesize = AsyncMock(side_effect=synthesize_side_effect)
        tool = SpeakTool(provider)

        import hashlib
        cache_key = "Brot\x00"
        filename = hashlib.md5(cache_key.encode()).hexdigest()[:12] + ".ogg"
        empty_cached = tmp_path / filename
        empty_cached.touch()  # 0 bytes → invalid cache entry

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result = await tool.execute(text="Brot")

        # Must have re-synthesized despite cache file existing (it was 0 bytes)
        assert call_count == 1
        assert result.endswith(".ogg")

    @pytest.mark.asyncio
    async def test_tts_generation_failure_returns_error_string(self, tmp_path):
        """TTS synthesis failure → SpeakTool returns descriptive error string, not an exception."""
        provider = AsyncMock()
        provider.synthesize = AsyncMock(side_effect=RuntimeError("disk full"))
        tool = SpeakTool(provider)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.tools.speak.get_media_dir", lambda _=None: tmp_path)
            result = await tool.execute(text="Schmetterling")

        assert "Error executing speak:" in result
        assert "disk full" in result
