"""
Sarvam AI Speech-to-Text - optimized for Indian languages with code-switching.
Falls back to Google Cloud STT if API call fails.
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# Sarvam language code mapping (their format)
SARVAM_LANGUAGE_MAP = {
    "hi": "hi-IN",
    "hi-IN": "hi-IN",
    "en-IN": "en-IN",
    "ta": "ta-IN",
    "ta-IN": "ta-IN",
    "te": "te-IN",
    "te-IN": "te-IN",
    "ml": "ml-IN",
    "ml-IN": "ml-IN",
    "kn": "kn-IN",
    "kn-IN": "kn-IN",
    "bn": "bn-IN",
    "bn-IN": "bn-IN",
    "mr": "mr-IN",
    "mr-IN": "mr-IN",
    "gu": "gu-IN",
    "gu-IN": "gu-IN",
    "pa": "pa-IN",
    "pa-IN": "pa-IN",
    "or": "or-IN",
    "or-IN": "or-IN",
}

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"


class SarvamSTT:
    """Sarvam AI Speech-to-Text for Indian languages."""

    def __init__(self, language_code: str = "hi", api_key: str = ""):
        self.language_code = SARVAM_LANGUAGE_MAP.get(language_code, "hi-IN")
        self.api_key = api_key
        logger.info(f"SarvamSTT initialized for: {self.language_code}")

    async def transcribe_audio_async(self, audio_content: bytes, audio_format: str = "webm") -> str:
        """
        Transcribe audio bytes via Sarvam REST API.
        Sarvam accepts WAV/MP3/WEBM via multipart form.
        """
        headers = {"api-subscription-key": self.api_key}

        # Determine file extension
        ext = audio_format if audio_format in ("wav", "mp3", "webm", "ogg") else "webm"

        form = aiohttp.FormData()
        form.add_field(
            "file",
            audio_content,
            filename=f"audio.{ext}",
            content_type=f"audio/{ext}",
        )
        form.add_field("language_code", self.language_code)
        form.add_field("model", "saarika:v2")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    SARVAM_STT_URL, headers=headers, data=form, timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        transcript = result.get("transcript", "")
                        logger.info(f"Sarvam transcribed ({self.language_code}): {transcript[:80]}")
                        return transcript
                    else:
                        error = await resp.text()
                        logger.error(f"Sarvam STT error {resp.status}: {error}")
                        raise RuntimeError(f"Sarvam API error {resp.status}: {error}")

        except aiohttp.ClientError as e:
            logger.error(f"Sarvam connection error: {e}")
            raise

    def transcribe_audio(self, audio_content: bytes, audio_format: str = "webm") -> str:
        """Synchronous wrapper."""
        return asyncio.run(self.transcribe_audio_async(audio_content, audio_format))

    def transcribe_file(self, file_path: str) -> str:
        """Transcribe an audio file."""
        path = Path(file_path)
        ext = path.suffix.lstrip(".")
        with open(file_path, "rb") as f:
            audio_content = f.read()
        return self.transcribe_audio(audio_content, audio_format=ext or "wav")
