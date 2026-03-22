"""
Gemini conversation engine with multi-language support.
"""

import vertexai
from vertexai.generative_models import GenerativeModel, ChatSession
from typing import Optional, List, Dict
import logging
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from src.conversation.prompts import (
    INTERVIEWER_SYSTEM_PROMPT,
    get_greeting,
    get_question,
    CLOSING_TEMPLATE_EN
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InterviewState:
    """Interview states."""
    NOT_STARTED = "not_started"
    GREETING = "greeting"
    QUESTION_1 = "question_1"
    QUESTION_2 = "question_2"
    QUESTION_3 = "question_3"
    CLOSING = "closing"
    COMPLETED = "completed"


class GeminiInterviewer:
    """Manages multi-language interviews using Gemini."""
    
    def __init__(self, language_code: str = "en"):
        """Initialize with specified language."""
        try:
            vertexai.init(
                project=settings.gcp_project_id,
                location=settings.gcp_location
            )
            
            self.model = GenerativeModel(
                model_name=settings.gemini_model,
                system_instruction=INTERVIEWER_SYSTEM_PROMPT
            )
            
            self.chat: Optional[ChatSession] = None
            self.language_code = language_code
            self.state = InterviewState.NOT_STARTED
            self.current_question = 0
            self.start_time: Optional[datetime] = None
            self.conversation_history: List[Dict[str, str]] = []
            
            logger.info(f"Gemini initialized for language: {language_code}")
            
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise
    
    def start_interview(self) -> str:
        """Start interview in configured language."""
        self.chat = self.model.start_chat()
        self.state = InterviewState.GREETING
        self.start_time = datetime.now()
        
        greeting = get_greeting(self.language_code)
        self._add_to_history("interviewer", greeting)
        
        return greeting
    
    def process_response(self, user_input: str) -> str:
        """Process user response and continue interview."""
        if not self.chat:
            raise RuntimeError("Interview not started")
        
        self._add_to_history("respondent", user_input)
        
        if self.state == InterviewState.GREETING:
            return self._ask_question(1)
        
        elif self.state in [InterviewState.QUESTION_1, InterviewState.QUESTION_2]:
            if self._should_move_to_next_question():
                return self._ask_question(self.current_question + 1)
            return self._get_ai_response(user_input)
        
        elif self.state == InterviewState.QUESTION_3:
            self.state = InterviewState.CLOSING
            return self.end_interview()
        
        return "Thank you."
    
    def _ask_question(self, question_number: int) -> str:
        """Ask specific question in configured language."""
        self.current_question = question_number
        
        if question_number == 1:
            self.state = InterviewState.QUESTION_1
        elif question_number == 2:
            self.state = InterviewState.QUESTION_2
        elif question_number == 3:
            self.state = InterviewState.QUESTION_3
        
        question = get_question(question_number, self.language_code)
        self._add_to_history("interviewer", question)
        
        return question
    
    def _get_ai_response(self, user_input: str) -> str:
        """Get AI follow-up in same language."""
        try:
            context = f"[Q{self.current_question}] User: {user_input}"
            response = self.chat.send_message(context)
            text = response.text
            
            self._add_to_history("interviewer", text)
            return text
        except Exception as e:
            logger.error(f"AI response error: {e}")
            return "Thank you for sharing. Let me ask the next question."
    
    def _should_move_to_next_question(self) -> bool:
        """Simple heuristic: 4+ messages in current question."""
        return len([m for m in self.conversation_history[-6:] 
                   if m.get("state") == self.state]) >= 4
    
    def end_interview(self) -> str:
        """End interview."""
        self.state = InterviewState.COMPLETED
        self._add_to_history("interviewer", CLOSING_TEMPLATE_EN)
        return CLOSING_TEMPLATE_EN
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get full conversation."""
        return self.conversation_history
    
    def _add_to_history(self, speaker: str, text: str):
        """Add to conversation history."""
        self.conversation_history.append({
            "speaker": speaker,
            "text": text,
            "timestamp": datetime.now().isoformat(),
            "state": self.state,
            "language": self.language_code
        })
