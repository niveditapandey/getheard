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

    def __init__(self, phone_number: str, language: str = "en"):
        self.phone_number = phone_number
        self.language = language
        self.interviewer = GeminiInterviewer(language_code=language)
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
            lang = detect_language(text)
            session = WhatsAppSession(from_number, language=lang)
            self.sessions[from_number] = session
            greeting = session.start()
            logger.info(f"[WA] New session {from_number} lang={lang}")
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
        try:
            self.transcript_manager.save(
                session_id=from_number.replace("whatsapp:", "").replace("+", ""),
                language_code=session.language,
                conversation=session.history(),
                metadata={"channel": "whatsapp", "phone_number": from_number},
            )
        except Exception as e:
            logger.error(f"[WA] Failed to save transcript: {e}")

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
