"""
Sarvam AI Text-to-Speech - natural voices for Indian languages.
"""

import asyncio
import base64
import logging

import aiohttp

logger = logging.getLogger(__name__)

# Sarvam language code mapping
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
}

# Best speaker per language (from Sarvam's current voice list)
SARVAM_SPEAKERS = {
    "hi-IN": "anushka",
    "en-IN": "anushka",
    "ta-IN": "anushka",
    "te-IN": "anushka",
    "ml-IN": "anushka",
    "kn-IN": "anushka",
    "bn-IN": "anushka",
    "mr-IN": "anushka",
    "gu-IN": "anushka",
    "pa-IN": "anushka",
}

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"


class SarvamTTS:
    """Sarvam AI Text-to-Speech for Indian languages."""

    def __init__(self, language_code: str = "hi", api_key: str = ""):
        self.language_code = SARVAM_LANGUAGE_MAP.get(language_code, "hi-IN")
        self.api_key = api_key
        self.speaker = SARVAM_SPEAKERS.get(self.language_code, "meera")
        logger.info(f"SarvamTTS initialized for: {self.language_code}, speaker: {self.speaker}")

    async def synthesize_speech_async(self, text: str) -> bytes:
        """Convert text to speech via Sarvam REST API. Returns MP3 bytes."""
        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "inputs": [text],
            "target_language_code": self.language_code,
            "speaker": self.speaker,
            "pitch": 0,
            "pace": 1.0,
            "loudness": 1.5,
            "speech_sample_rate": 22050,
            "enable_preprocessing": True,
            "model": "bulbul:v2",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                SARVAM_TTS_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    # Sarvam returns list of base64-encoded audio chunks
                    audios = result.get("audios", [])
                    if not audios:
                        raise RuntimeError("Sarvam TTS returned no audio")
                    audio_bytes = base64.b64decode(audios[0])
                    logger.info(f"Sarvam synthesized {len(text)} chars → {len(audio_bytes)} bytes")
                    return audio_bytes
                else:
                    error = await resp.text()
                    logger.error(f"Sarvam TTS error {resp.status}: {error}")
                    raise RuntimeError(f"Sarvam TTS API error {resp.status}: {error}")

    def synthesize_speech(self, text: str) -> bytes:
        """Synchronous wrapper."""
        return asyncio.run(self.synthesize_speech_async(text))

    def save_to_file(self, text: str, output_path: str) -> None:
        """Synthesize and save to file."""
        audio_bytes = self.synthesize_speech(text)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
        logger.info(f"Sarvam audio saved to: {output_path}")
