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
