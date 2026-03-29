"""
WhatsApp text interview handler.
Connects WhatsApp messages to Gemini conversation engine via Twilio.

Flow: User sends WhatsApp msg → Twilio webhook → here → Gemini → reply
Same Gemini engine as voice, just text instead of audio.
"""

import logging
from typing import Dict, Optional

from langdetect import detect, LangDetectException

from src.conversation.gemini_engine import GeminiInterviewer
from src.storage.transcript import TranscriptManager

logger = logging.getLogger(__name__)

# Map langdetect codes → our supported language codes
LANGDETECT_MAP = {
    "hi": "hi",
    "id": "id",
    "tl": "fil",
    "th": "th",
    "vi": "vi",
    "ko": "ko",
    "ja": "ja",
    "zh-cn": "zh",
    "zh-tw": "zh",
    "en": "en",
}


def detect_language(text: str) -> str:
    """Detect language from text, fall back to English."""
    try:
        lang = detect(text)
        return LANGDETECT_MAP.get(lang, "en")
    except LangDetectException:
        return "en"


class WhatsAppSession:
    """Tracks a single WhatsApp interview session."""

    def __init__(self, phone_number: str, language: str = "en", project_id: Optional[str] = None):
        self.phone_number = phone_number
        self.language = language
        self.project_id = project_id

        custom_questions = None
        project_name = None
        if project_id:
            try:
                from src.core.research_project import get_project
                proj = get_project(project_id)
                if proj:
                    custom_questions = proj.questions
                    project_name = proj.name
                    logger.info(f"[WA] Loaded {len(custom_questions)} questions from project '{project_name}'")
            except Exception as e:
                logger.warning(f"[WA] Could not load project {project_id}: {e}")

        self.interviewer = GeminiInterviewer(
            language_code=language,
            custom_questions=custom_questions,
            project_name=project_name,
        )
        self.started = False

    def start(self) -> str:
        self.started = True
        return self.interviewer.start_interview()

    def respond(self, text: str) -> str:
        return self.interviewer.process_response(text)

    def end(self) -> str:
        return self.interviewer.end_interview()

    def is_complete(self) -> bool:
        return self.interviewer.state == "completed"

    def history(self):
        return self.interviewer.get_conversation_history()


class WhatsAppInterviewManager:
    """
    Manages text-based interviews via WhatsApp.
    In-memory sessions (use Redis in production).
    """

    HELP_MSG = (
        "👋 Welcome to GetHeard! I'll ask you a few questions about your "
        "healthcare experience.\n\n"
        "Commands:\n"
        "• Any message → start/continue interview\n"
        "• *stop* → end interview\n"
        "• *lang:hi* → switch to Hindi\n"
        "• *lang:id* → switch to Indonesian\n"
        "• *lang:th* → switch to Thai"
    )

    def __init__(self):
        self.sessions: Dict[str, WhatsAppSession] = {}
        self.transcript_manager = TranscriptManager()
        logger.info("WhatsApp Interview Manager ready")

    def handle_message(self, from_number: str, body: str) -> str:
        """
        Process an incoming WhatsApp message and return reply text.
        """
        text = body.strip()
        lower = text.lower()

        # ── Commands ──────────────────────────────────────────────
        if lower in ("stop", "end", "quit", "cancel", "bye"):
            return self._stop(from_number)

        if lower in ("help", "?"):
            return self.HELP_MSG

        # Language switch: "lang:hi", "lang:id", etc.
        if lower.startswith("lang:"):
            lang = lower.split(":", 1)[1].strip()
            return self._switch_language(from_number, lang)

        # ── New session ───────────────────────────────────────────
        if from_number not in self.sessions:
            project_id = None
            # Support "START <project_id>" to route into a specific study
            if lower.startswith("start"):
                parts = text.split(None, 1)
                if len(parts) > 1:
                    project_id = parts[1].strip()
                    lang = "en"
                else:
                    lang = detect_language(text)
            else:
                lang = detect_language(text)
            session = WhatsAppSession(from_number, language=lang, project_id=project_id)
            self.sessions[from_number] = session
            greeting = session.start()
            logger.info(f"[WA] New session {from_number} lang={lang} project={project_id}")
            return greeting

        # ── Existing session ──────────────────────────────────────
        session = self.sessions[from_number]
        response = session.respond(text)

        if session.is_complete():
            self._save_and_clean(from_number)

        return response

    def _stop(self, from_number: str) -> str:
        if from_number not in self.sessions:
            return "No active interview. Send any message to start one!"
        session = self.sessions[from_number]
        closing = session.end()
        self._save_and_clean(from_number)
        return closing

    def _switch_language(self, from_number: str, lang: str) -> str:
        supported = ["en", "hi", "id", "fil", "th", "vi", "ko", "ja", "zh"]
        if lang not in supported:
            return f"Supported languages: {', '.join(supported)}"
        # Kill old session, start fresh in new language
        if from_number in self.sessions:
            del self.sessions[from_number]
        session = WhatsAppSession(from_number, language=lang)
        self.sessions[from_number] = session
        greeting = session.start()
        return f"Switched to {lang}!\n\n{greeting}"

    def _save_and_clean(self, from_number: str):
        session = self.sessions.pop(from_number, None)
        if not session:
            return
        session_id = from_number.replace("whatsapp:", "").replace("+", "")
        try:
            self.transcript_manager.save(
                session_id=session_id,
                language_code=session.language,
                conversation=session.history(),
                metadata={
                    "channel": "whatsapp",
                    "phone_number": from_number,
                    "project_id": session.project_id,
                },
            )
            # Register session in the project record
            if session.project_id:
                try:
                    from src.core.research_project import get_project
                    proj = get_project(session.project_id)
                    if proj:
                        proj.add_session(session_id)
                except Exception as e:
                    logger.warning(f"[WA] add_session failed: {e}")
        except Exception as e:
            logger.error(f"[WA] Failed to save transcript: {e}")

        # Auto-credit points if respondent is enrolled in the panel
        try:
            clean_phone = from_number.replace("whatsapp:", "")
            from src.storage.respondent_store import _find_by_phone
            respondent = _find_by_phone(clean_phone)
            if respondent:
                from src.storage.points_store import add_points
                add_points(
                    respondent_id=respondent["respondent_id"],
                    amount=50,
                    reason="WhatsApp interview completed",
                    study_id=session.project_id or "",
                )
                logger.info(f"[WA] Credited 50 pts to respondent {respondent['respondent_id']}")
        except Exception as e:
            logger.warning(f"[WA] Points credit failed: {e}")

    # ── Stats ─────────────────────────────────────────────────────
    def active_count(self) -> int:
        return len(self.sessions)

    def active_numbers(self) -> list:
        return list(self.sessions.keys())


# Singleton
_manager: Optional[WhatsAppInterviewManager] = None


def get_whatsapp_manager() -> WhatsAppInterviewManager:
    global _manager
    if _manager is None:
        _manager = WhatsAppInterviewManager()
    return _manager
