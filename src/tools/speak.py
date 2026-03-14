"""Speak tool for generating German audio pronunciation."""

import hashlib
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.config.paths import get_media_dir

from src.tts.base import TTSProvider


class SpeakTool(Tool):
    """Tool to generate German speech audio using a TTS provider."""

    def __init__(self, tts_provider: TTSProvider) -> None:
        self._tts = tts_provider

    @property
    def name(self) -> str:
        return "speak"

    @property
    def description(self) -> str:
        return (
            "Generate German audio pronunciation. Use this to help the student "
            "hear how words or sentences sound in German. Returns a file path — "
            "include it in the message tool's media array to send as a voice message."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The German text to speak aloud"
                },
                "voice": {
                    "type": "string",
                    "description": "Optional voice ID (default: de-DE-ConradNeural)"
                }
            },
            "required": ["text"]
        }

    async def execute(self, text: str, voice: str | None = None, **kwargs: Any) -> str:
        try:
            media_dir = get_media_dir("tts")
            filename = hashlib.md5(text.encode()).hexdigest()[:12] + ".ogg"
            output_path = str(media_dir / filename)

            if Path(output_path).exists():
                return output_path

            await self._tts.synthesize(text, output_path, voice=voice)
            return output_path
        except Exception as e:
            return f"Error executing speak: {e}"
