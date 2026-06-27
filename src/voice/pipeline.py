"""
Voice interview pipeline - orchestrates STT → Gemini → TTS for any language.
Handles provider routing: Sarvam for Indian languages, Google Cloud for others.

All public methods are async so they integrate cleanly with FastAPI.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

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

        # Conversation engine — use InterviewAgent when a project is linked
        self.agent = None  # InterviewAgent (preferred)
        self.interviewer = None  # GeminiInterviewer (fallback)

        if project_id:
            try:
                from src.agents.orchestrator import orchestrator as _orc
                self.agent = _orc.create_interview_agent(project_id)
                if self.agent:
                    logger.info(f"[{self.session_id}] Using InterviewAgent for project {project_id}")
            except Exception as e:
                logger.warning(f"[{self.session_id}] InterviewAgent load failed, falling back: {e}")

        if self.agent is None:
            # Fallback: load questions manually for GeminiInterviewer
            custom_questions = None
            project_name = None
            if project_id:
                proj = get_project(project_id)
                if proj:
                    custom_questions = proj.questions
                    project_name = proj.name
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

    # ── Public API ────────────────────────────────────────────────────────────

    async def start_interview(self) -> bytes:
        """
        Generate the opening greeting and convert to audio.
        Returns MP3 audio bytes.
        """
        if self.agent:
            greeting_text = self.agent.get_opening()
        else:
            greeting_text = await asyncio.to_thread(self.interviewer.start_interview)

        audio_bytes = await asyncio.to_thread(self.tts.synthesize_speech, greeting_text)
        self.is_started = True
        logger.info(f"[{self.session_id}] Interview started | greeting={greeting_text[:60]}…")
        return audio_bytes

    async def process_audio(
        self,
        audio_bytes: bytes,
        audio_format: str = "webm",
    ) -> Tuple[str, bytes, bool, int]:
        """
        Full STT → LLM → TTS pipeline for one respondent turn.

        Returns:
            transcript_text   — what the respondent said (transcribed)
            response_audio    — interviewer's reply as MP3 bytes
            is_complete       — True when the interview is finished
            current_q_idx     — 0-based index of the current question
        """
        # ── 1. Speech → Text ─────────────────────────────────────────────────
        try:
            transcript = await asyncio.to_thread(
                self.stt.transcribe_audio, audio_bytes, audio_format
            )
        except Exception as e:
            logger.error(f"[{self.session_id}] STT error: {e}")
            transcript = ""

        if not transcript.strip():
            transcript = "[inaudible]"

        # ── 2. Text → Next interviewer turn ──────────────────────────────────
        try:
            if self.agent:
                response_text, is_complete = await self.agent.process_response(transcript)
                current_q_idx = self.agent.current_q_idx
            else:
                response_text = await asyncio.to_thread(
                    self.interviewer.process_response, transcript
                )
                is_complete = self.interviewer.state == GeminiInterviewer.COMPLETED
                current_q_idx = self.interviewer.current_question_idx
        except Exception as e:
            logger.error(f"[{self.session_id}] LLM error: {e}")
            response_text = "Could you tell me a bit more about that?"
            is_complete = False
            current_q_idx = 0

        # ── 3. Text → Speech ─────────────────────────────────────────────────
        try:
            response_audio = await asyncio.to_thread(
                self.tts.synthesize_speech, response_text
            )
        except Exception as e:
            logger.error(f"[{self.session_id}] TTS error: {e}")
            response_audio = b""

        # ── 4. Auto-save transcript on completion ─────────────────────────────
        if is_complete:
            try:
                await asyncio.to_thread(self._save_transcript)
                logger.info(f"[{self.session_id}] Transcript auto-saved on completion")
            except Exception as e:
                logger.warning(f"[{self.session_id}] Auto-save failed: {e}")

        return transcript, response_audio, is_complete, current_q_idx

    def get_conversation_history(self) -> List[Dict]:
        """Return the full conversation as a list of turn dicts."""
        if self.agent:
            return list(self.agent.conversation)
        return self.interviewer.get_conversation_history()

    def get_provider_info(self) -> Dict:
        """Return the STT/TTS provider names for this session."""
        return {
            "stt": self._stt_provider,
            "tts": self._tts_provider,
            "llm": "gemini",
            "engine": "InterviewAgent" if self.agent else "GeminiInterviewer",
            "session_id": self.session_id,
        }

    def is_interview_complete(self) -> bool:
        """True when the interview has ended."""
        if self.agent:
            return bool(self.agent.is_complete)
        return self.interviewer.state == GeminiInterviewer.COMPLETED

    def _save_transcript(self) -> None:
        """Persist the conversation to Firestore via TranscriptManager."""
        history = self.get_conversation_history()
        self.transcript_manager.save(
            session_id=self.session_id,
            language_code=self.language_code,
            conversation=history,
            metadata={
                "started_at":    self.started_at,
                "project_id":    self.project_id,
                "stt_provider":  self._stt_provider,
                "tts_provider":  self._tts_provider,
                "engine":        "InterviewAgent" if self.agent else "GeminiInterviewer",
            },
        )
        logger.info(f"[{self.session_id}] Transcript saved | turns={len(history)}")
