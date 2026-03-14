"""Piper TTS provider — local, offline synthesis via subprocess."""

import asyncio
from pathlib import Path

from loguru import logger

from src.audio import convert_to_ogg_opus
from src.tts.base import TTSProvider


class PiperTTSProvider(TTSProvider):
    """
    Text-to-Speech provider using Piper (piper-tts package).

    Runs inference locally on CPU; no network required after the model is
    downloaded.  The model is fetched automatically by the piper CLI on first
    use and cached in ~/.local/share/piper (or the path set by PIPER_DATA_DIR).

    Defaults to the high-quality Thorsten German voice.
    """

    DEFAULT_MODEL = "de_DE-thorsten-high"

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    async def synthesize(self, text: str, output_path: str, voice: str | None = None) -> str:
        """
        Synthesize *text* to an OGG Opus file using the piper CLI.

        Piper writes WAV output; we convert it to OGG Opus with ffmpeg so the
        file can be sent as a Telegram voice message.

        Args:
            text: The German text to synthesize.
            output_path: Destination path for the .ogg file.
            voice: Ignored for Piper (model selection is done at construction
                   time); kept for interface compatibility.

        Returns:
            output_path on success.

        Raises:
            RuntimeError: If piper is not installed or exits with a non-zero
                          return code.
            Exception: Propagates any other error from piper or ffmpeg.
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        tmp_wav = str(output.with_suffix(".wav"))

        try:
            proc = await asyncio.create_subprocess_exec(
                "piper",
                "--model", self.model,
                "--output_file", tmp_wav,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate(input=text.encode())

            if proc.returncode != 0:
                err = stderr.decode(errors="replace").strip()
                raise RuntimeError(f"piper exited with code {proc.returncode}: {err}")

            await convert_to_ogg_opus(tmp_wav, output_path)
            return output_path
        except FileNotFoundError as exc:
            raise RuntimeError(
                "piper not found — install it with: pip install piper-tts"
            ) from exc
        except Exception:
            logger.exception("PiperTTS synthesis error for model={}", self.model)
            raise
        finally:
            Path(tmp_wav).unlink(missing_ok=True)
