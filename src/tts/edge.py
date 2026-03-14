"""Edge TTS provider implementation using Microsoft neural voices."""

from pathlib import Path

import edge_tts
from loguru import logger

from src.audio import convert_to_ogg_opus
from src.tts.base import TTSProvider


class EdgeTTSProvider(TTSProvider):
    """
    Text-to-Speech provider using the edge-tts library.

    Uses Microsoft's neural voices via the unofficial Edge TTS API.
    Defaults to de-DE-ConradNeural for German lessons.
    """

    DEFAULT_VOICE = "de-DE-ConradNeural"

    def __init__(self, voice: str = DEFAULT_VOICE):
        self.voice = voice

    async def synthesize(self, text: str, output_path: str, voice: str | None = None) -> str:
        """
        Synthesize text to an OGG Opus file using edge-tts.

        Downloads MP3 from Microsoft's TTS API, then converts to OGG Opus
        via ffmpeg so it can be sent as a Telegram voice message.

        Args:
            text: The German text to synthesize.
            output_path: Destination path for the .ogg file.
            voice: Optional voice override; falls back to self.voice.

        Returns:
            output_path on success.

        Raises:
            Exception: Propagates any exception raised by edge-tts or ffmpeg.
        """
        v = voice or self.voice
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        tmp_mp3 = str(output.with_suffix(".mp3"))

        try:
            communicate = edge_tts.Communicate(text, v)
            await communicate.save(tmp_mp3)
            await convert_to_ogg_opus(tmp_mp3, output_path)
            return output_path
        except Exception:
            logger.exception("EdgeTTS synthesis error for voice={}", v)
            raise
        finally:
            Path(tmp_mp3).unlink(missing_ok=True)
