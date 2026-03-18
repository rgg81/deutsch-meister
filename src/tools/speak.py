"""Speak tool for generating German audio pronunciation."""

import hashlib
import os
import tempfile
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
                    "description": "Optional voice ID (defaults to the provider's configured voice)"
                }
            },
            "required": ["text"]
        }

    async def execute(self, text: str, voice: str | None = None, **kwargs: Any) -> str:
        try:
            media_dir = get_media_dir("tts")
            cache_key = f"{text}\x00{voice or ''}"
            filename = hashlib.md5(cache_key.encode()).hexdigest()[:12] + ".ogg"
            output_path = Path(media_dir) / filename

            if output_path.exists() and output_path.stat().st_size > 0:
                return str(output_path)

            tmp_fd, tmp_path = tempfile.mkstemp(dir=media_dir, suffix=".tmp.ogg")
            os.close(tmp_fd)
            try:
                await self._tts.synthesize(text, tmp_path, voice=voice)
                os.replace(tmp_path, output_path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

            return str(output_path)
        except Exception as e:
            return f"Error executing speak: {e}"
