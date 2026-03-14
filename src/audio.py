"""Audio format conversion helpers."""

import asyncio


async def convert_to_ogg_opus(input_path: str, output_path: str) -> str:
    """
    Convert an audio file to OGG Opus format suitable for Telegram voice messages.

    Uses ffmpeg to encode as Opus at 48kHz mono 48kbps — the format expected
    by Telegram's sendVoice API.

    Args:
        input_path: Path to the source audio file (e.g. MP3 or WAV).
        output_path: Destination path for the .ogg file.

    Returns:
        output_path on success.

    Raises:
        RuntimeError: If ffmpeg exits with a non-zero return code.
    """
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", input_path,
        "-acodec", "libopus", "-b:a", "48k",
        "-ar", "48000", "-ac", "1",
        output_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    returncode = await proc.wait()
    if returncode != 0:
        raise RuntimeError(f"ffmpeg exited with code {returncode} converting {input_path!r} to OGG Opus")
    return output_path
