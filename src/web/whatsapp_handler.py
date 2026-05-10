"""
WhatsApp interview handler — routes Twilio messages to InterviewAgent.

Flow:
  Twilio webhook → handle_message() → InterviewAgent.process_response() → TwiML reply

Sessions are keyed by phone number (from Twilio's From field).
Project routing: "START <project_id>" or pre-linked via /join page.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
PROJECTS_DIR = BASE_DIR / "projects"


class WhatsAppSession:
    """Tracks a single WhatsApp interview session backed by InterviewAgent."""

    def __init__(self, phone_number: str, project_id: str):
        self.phone_number = phone_number
        self.project_id = project_id
        self.agent = None
        self.started = False

    def _load_agent(self):
        from src.agents.orchestrator import orchestrator
        self.agent = orchestrator.create_interview_agent(self.project_id)
        if self.agent is None:
            raise ValueError(f"Project not found: {self.project_id}")

    def start(self) -> str:
        self._load_agent()
        self.started = True
        opening = self.agent.get_opening()
        logger.info(f"[WA] Session started: {self.phone_number} project={self.project_id}")
        return opening

    async def respond(self, text: str):
        """Returns (reply_text, is_complete)."""
        return await self.agent.process_response(text)

    def is_complete(self) -> bool:
        return self.agent.is_complete if self.agent else False

    def conversation(self):
        return self.agent.conversation if self.agent else []


class WhatsAppInterviewManager:
    """
    In-memory registry of active WhatsApp interview sessions.
    Each phone number maps to one active WhatsAppSession.
    """

    HELP_TEXT = (
        "👗 Welcome to GetHeard!\n\n"
        "To start an interview, send:\n"
        "  *START <study_id>*\\n\n"
        "Commands:\n"
        "  stop — end interview early\n"
        "  help — show this message"
    )

    def __init__(self):
        self.sessions: Dict[str, WhatsAppSession] = {}
        # phone_number → project_id mapping (set when respondent joins via /join link)
        self._phone_project_map: Dict[str, str] = {}
        logger.info("[WA] WhatsApp Interview Manager ready")

    def register_phone(self, phone_number: str, project_id: str):
        """Called when a respondent submits their number on the /join page."""
        self._phone_project_map[phone_number] = project_id
        logger.info(f"[WA] Registered {phone_number} → project {project_id}")

    async def handle_message(self, from_number: str, body: str) -> str:
        text = body.strip()
        lower = text.lower()

        if lower in ("stop", "end", "quit", "bye"):
            return await self._stop(from_number)

        if lower in ("help", "?", ""):
            return self.HELP_TEXT

        # START <project_id> command
        if lower.startswith("start"):
            parts = text.split(None, 1)
            project_id = parts[1].strip() if len(parts) > 1 else None
            if not project_id:
                return "Please send: *START <study_id>*  (look for it in the invitation link)"
            return await self._begin_session(from_number, project_id)

        # Existing session
        if from_number in self.sessions:
            return await self._continue_session(from_number, text)

        # Check if phone was pre-registered via /join page
        if from_number in self._phone_project_map:
            project_id = self._phone_project_map[from_number]
            return await self._begin_session(from_number, project_id)

        # Unknown user ┐ prompt
        return (
            "👗 Hi! I'm the GetHeard AI interviewer.\n\n"
            "To start your interview, send:\n"
            "  *START <study_id>*\\n\n"
            "You'll find the study ID in the link you received."
        )

    async def _begin_session(self, from_number: str, project_id: str) -> str:
        try:
            session = WhatsAppSession(from_number, project_id)
            opening = session.start()
            self.sessions[from_number] = session
            return opening
        except ValueError as e:
            logger.warning(f"[WA] Session start failed for {from_number}: {e}")
            return f"Sorry, I couldn't find that study. Please check the study ID and try again."
        except Exception as e:
            logger.error(f"[WA] Session start error: {e}", exc_info=True)
            return "Sorry, something went wrong starting your interview. Please try again."

    async def _continue_session(self, from_number: str, text: str) -> str:
        session = self.sessions[from_number]
        try:
            reply, is_done = await session.respond(text)
            if is_done:
                await self._save_and_clean(from_number)
            return reply
        except Exception as e:
            logger.error(f"[WA] Response error for {from_number}: {e}", exc_info=True)
            return "Sorry, I had trouble with that. Could you say that again?"

    async def _stop(self, from_number: str) -> str:
        if from_number not in self.sessions:
            return "No active interview. Send *START <study_id>* to begin."
        await self._save_and_clean(from_number)
        return "Thank you for your time! Your responses have been saved. Have a great day! 😊"

    async def _save_and_clean(self, from_number: str):
        session = self.sessions.pop(from_number, None)
        self._phone_project_map.pop(from_number, None)
        if not session:
            return

        clean_phone = from_number.replace("whatsapp:", "").replace("+", "")
        conversation = session.conversation()

        try:
            from src.storage.transcript import TranscriptManager
            tm = TranscriptManager()
            tm.save(
                session_id=clean_phone,
                language_code=session.agent.language if session.agent else "en",
                conversation=conversation,
                metadata={
                    "channel": "whatsapp",
                    "phone_number": from_number,
                    "project_id": session.project_id,
                },
            )
            if session.project_id:
                from src.core.research_project import get_project
                proj = get_project(session.project_id)
                if proj:
                    proj.add_session(clean_phone)
        except Exception as e:
            logger.error(f"[WA] Transcript save failed: {e}", exc_info=True)

        # Credit points if respondent is in panel
        try:
            from src.storage.respondent_store import _find_by_phone
            respondent = _find_by_phone(from_number.replace("whatsapp:", ""))
            if respondent:
                from src.storage.points_store import add_points
                add_points(
                    respondent_id=respondent["respondent_id"],
                    amount=50,
                    reason="WhatsApp interview completed",
                    study_id=session.project_id or "",
                )
        except Exception as e:
            logger.warning(f"[WA] Points credit failed: {e}")

    def active_count(self) -> int:
        return len(self.sessions)

    def active_numbers(self) -> list:
        return list(self.sessions.keys())


_manager: Optional[WhatsAppInterviewManager] = None


def get_whatsapp_manager() -> WhatsAppInterviewManager:
    global _manager
    if _manager is None:
        _manager = WhatsAppInterviewManager()
    return _manager
