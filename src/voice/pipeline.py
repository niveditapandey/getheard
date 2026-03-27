"""
Voice interview pipeline - orchestrates STT → Gemini → TTS for any language.
Handles provider routing: Sarvam for Indian languages, Google Cloud for others.

All public methods are async so they integrate cleanly with FastAPI.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional, Tuple

from config.settings import settings
from src.conversation.gemini_engine import GeminiInterviewer
from src.core.research_project import get_project
from src.storage.transcript import TranscriptManager
from src.voice.google_cloud_stt import GoogleCloudSTT
from src.voice.google_cloud_tts import GoogleCloudTTS

logger = logging.getLogger(__name__)


class VoiceInterviewPipeline:
    """
    Orchestrates the full interview pipeline for a single session.
    Provider-aware: auto-routes to Sarvam for Indian languages.
    All I/O methods are async.
    """

    def __init__(self, language_code: str = "en", project_id: Optional[str] = None):
        self.session_id = str(uuid.uuid4())[:8]
        self.language_code = language_code
        self.project_id = project_id
        self.started_at = datetime.now().isoformat()
        self.is_started = False

        use_sarvam = settings.should_use_sarvam(language_code)

        # Initialise STT
        if use_sarvam:
            from src.voice.sarvam_stt import SarvamSTT
            self.stt = SarvamSTT(language_code=language_code, api_key=settings.sarvam_api_key)
            self._stt_provider = "sarvam"
        else:
            self.stt = GoogleCloudSTT(language_code=language_code)
            self._stt_provider = "google"

        # Initialise TTS
        if use_sarvam:
            from src.voice.sarvam_tts import SarvamTTS
            self.tts = SarvamTTS(language_code=language_code, api_key=settings.sarvam_api_key)
            self._tts_provider = "sarvam"
        else:
            self.tts = GoogleCloudTTS(language_code=language_code)
            self._tts_provider = "google"

        # Load custom questions from project if supplied
        custom_questions = None
        project_name = None
        if project_id:
            proj = get_project(project_id)
            if proj:
                custom_questions = proj.questions
                project_name = proj.name
                logger.info(f"[{self.session_id}] Loaded {len(custom_questions)} questions from project '{project_name}'")

        # Conversation engine and transcript manager
        self.interviewer = GeminiInterviewer(
            language_code=language_code,
            custom_questions=custom_questions,
            project_name=project_name,
        )
        self.transcript_manager = TranscriptManager()

        logger.info(
            f"[{self.session_id}] Pipeline ready | lang={language_code} | "
            f"STT={self._stt_provider} | TTS={self._tts_provider}"
        )

    # -----------------------------------------------------------------------
    # Public async API
    # -----------------------------------------------------------------------

    async def start_interview(self) -> bytes:
        """Start the interview and return the greeting as audio bytes (MP3)."""
        greeting_text = await asyncio.to_thread(self.interviewer.start_interview)
        audio = await self._synthesize(greeting_text)
        self.is_started = True
        logger.info(f"[{self.session_id}] Interview started")
        return audio

    async def process_audio(
        self, audio_content: bytes, audio_format: str = "webm"
    ) -> Tuple[str, bytes, bool]:
        """
        Process user audio and return (transcript, response_audio, is_complete).

        Args:
            audio_content: Raw audio bytes from the browser.
            audio_format:  Container format hint ("webm", "wav", "mp3").
        """
        if not self.is_started:
            raise RuntimeError("Call start_interview() first.")

        # 1. Transcribe
        transcript = await self._transcribe(audio_content, audio_format)
        logger.info(f"[{self.session_id}] User: {transcript[:120]}")

        # 2. Generate AI response (Gemini is sync — run in thread)
        response_text = await asyncio.to_thread(
            self.interviewer.process_response, transcript
        )
        logger.info(f"[{self.session_id}] AI: {response_text[:120]}")

        # 3. Synthesise
        response_audio = await self._synthesize(response_text)

        is_complete = self.is_interview_complete()
        if is_complete:
            await asyncio.to_thread(self._save_transcript)

        return transcript, response_audio, is_complete

    def is_interview_complete(self) -> bool:
        return self.interviewer.state == "completed"

    def get_conversation_history(self):
        return self.interviewer.get_conversation_history()

    def get_provider_info(self) -> dict:
        return {
            "language": self.language_code,
            "session_id": self.session_id,
            "stt_provider": self._stt_provider,
            "tts_provider": self._tts_provider,
        }

    # -----------------------------------------------------------------------
    # Private async helpers
    # -----------------------------------------------------------------------

    async def _transcribe(self, audio_content: bytes, audio_format: str) -> str:
        """Transcribe with fallback to Google Cloud if primary fails."""
        try:
            if self._stt_provider == "sarvam":
                return await self.stt.transcribe_audio_async(audio_content, audio_format=audio_format)
            else:
                # Google STT is sync — run in thread
                return await asyncio.to_thread(self.stt.transcribe_audio, audio_content, audio_format)
        except Exception as e:
            logger.warning(f"[{self.session_id}] Primary STT failed ({type(e).__name__}: {e}), falling back to Google")
            fallback = GoogleCloudSTT(language_code=self.language_code)
            return await asyncio.to_thread(fallback.transcribe_audio, audio_content, audio_format)

    async def _synthesize(self, text: str) -> bytes:
        """Synthesize TTS with fallback to Google Cloud if primary fails."""
        try:
            if self._tts_provider == "sarvam":
                return await self.tts.synthesize_speech_async(text)
            else:
                # Google TTS is sync — run in thread
                return await asyncio.to_thread(self.tts.synthesize_speech, text)
        except Exception as e:
            logger.warning(f"[{self.session_id}] Primary TTS failed ({type(e).__name__}: {e}), falling back to Google")
            fallback = GoogleCloudTTS(language_code=self.language_code)
            return await asyncio.to_thread(fallback.synthesize_speech, text)

    def _save_transcript(self):
        try:
            filepath = self.transcript_manager.save(
                session_id=self.session_id,
                language_code=self.language_code,
                conversation=self.get_conversation_history(),
                metadata={
                    "started_at": self.started_at,
                    "stt_provider": self._stt_provider,
                    "tts_provider": self._tts_provider,
                    "project_id": self.project_id,
                },
            )
            logger.info(f"[{self.session_id}] Transcript saved → {filepath}")
        except Exception as e:
            logger.error(f"[{self.session_id}] Failed to save transcript: {e}")
