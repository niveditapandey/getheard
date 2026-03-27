"""
BriefAgent — Conversational research brief intake.

Replaces the static web form with a chat-based consultant experience.
The agent asks ONE question at a time, probes vague answers, and only
saves the brief after the client confirms all details are correct.

Usage:
    agent = BriefAgent()

    # In a chat loop:
    response = await agent.message("I want to understand why our app users churn")
    # Keep calling agent.message() until agent.brief_saved is True
    brief = agent.collected_brief   # Dict with all fields
"""

import logging
from typing import Dict, List, Optional

from config.settings import settings
from .base_agent import BaseAgent, ToolSpec

logger = logging.getLogger(__name__)

BRIEF_SYSTEM_PROMPT = """You are Alex, a senior research consultant at GetHeard — a qualitative research firm specialising in Asian consumer markets.

Your job: have a warm, professional conversation with a client to collect their research brief, then produce a structured research specification.

━━ CONVERSATION RULES ━━
• Ask ONE question at a time — never list multiple questions in one message
• Be genuinely curious — this is a conversation, not a form
• Probe vague answers before moving on ("What do you mean by 'not working'?", "Can you give me an example?")
• Suggest research types when the client describes their problem (e.g. "That sounds like a CX deep-dive")
• Confirm the brief back to the client before saving — summarise what you've collected and ask "Does that capture it correctly?"
• Only call save_brief() after the client confirms

━━ INFORMATION TO COLLECT ━━
Collect all of these naturally through conversation (never show this list to the client):
  project_name    → A short name for this project
  research_type   → cx / ux / brand / product / nps / employee / market / custom
  industry        → Their industry/sector
  objective       → The core question this research must answer (specific, not vague)
  target_audience → Who the respondents are (segment, demographics, relationship to brand)
  language        → Interview language: en / hi / id / fil / th / vi / ko / ja / zh
  topics          → 3–6 key areas to explore (list)
  question_count  → Number of interview questions (5, 7, 10, 12, 15, 20, 25, or 30)

━━ RESEARCH TYPE GUIDE ━━
  cx       → Customer Experience (journeys, touchpoints, pain points)
  ux       → User Experience (product/app usability, flows)
  brand    → Brand Perception (awareness, associations, trust)
  product  → Product Feedback (features, bugs, wishlist)
  nps      → NPS Deep-Dive (drivers of promoters vs detractors)
  employee → Employee Satisfaction (culture, management, retention)
  market   → Market Research (category, competitors, unmet needs)
  custom   → Anything else

━━ TONE ━━
Warm, expert, concise. You're a trusted consultant, not a chatbot. Use the client's language, not jargon."""


class BriefAgent(BaseAgent):
    """
    Conversational agent that collects a research brief through chat.

    The agent maintains conversation state across multiple .message() calls.
    When brief_saved is True, collected_brief contains the structured brief.
    """

    def __init__(self):
        super().__init__()
        self.name = "BriefAgent"
        self.model = settings.gemini_model  # flash — conversational, must feel instant
        self.system_prompt = BRIEF_SYSTEM_PROMPT
        self.brief_saved: bool = False
        self.collected_brief: Optional[Dict] = None
        self._turn_count: int = 0

        self.register_tool(ToolSpec(
            name="save_brief",
            description=(
                "Save the finalised research brief. "
                "Only call this AFTER the client has confirmed all details are correct."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Short name for the research project",
                    },
                    "research_type": {
                        "type": "string",
                        "enum": ["cx", "ux", "brand", "product", "nps", "employee", "market", "custom"],
                    },
                    "industry": {"type": "string"},
                    "objective": {
                        "type": "string",
                        "description": "The specific research question this study must answer",
                    },
                    "target_audience": {
                        "type": "string",
                        "description": "Who the respondents are",
                    },
                    "language": {
                        "type": "string",
                        "enum": ["en", "hi", "id", "fil", "th", "vi", "ko", "ja", "zh"],
                    },
                    "topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key topic areas to explore in the interview",
                    },
                    "question_count": {
                        "type": "integer",
                        "description": "Number of questions: 5, 7, 10, 12, 15, 20, 25, or 30",
                    },
                },
                "required": [
                    "project_name", "research_type", "industry", "objective",
                    "target_audience", "language", "topics", "question_count",
                ],
            },
            handler=self._save_brief_handler,
        ))

    async def _save_brief_handler(
        self,
        project_name: str,
        research_type: str,
        industry: str,
        objective: str,
        target_audience: str,
        language: str,
        topics: List[str],
        question_count: int,
    ) -> Dict:
        self.collected_brief = {
            "project_name": project_name,
            "research_type": research_type,
            "industry": industry,
            "objective": objective,
            "target_audience": target_audience,
            "language": language,
            "topics": topics,
            "question_count": question_count,
        }
        self.brief_saved = True
        logger.info(f"[BriefAgent] Brief saved: {project_name} ({research_type})")
        return {"status": "saved", "project_name": project_name}

    async def message(self, user_input: str) -> str:
        """
        Send a user message and get the agent's conversational response.
        After brief_saved is True, the conversation is complete.
        """
        self._turn_count += 1

        # First turn: prime the agent with a greeting if the user just says hello
        if self._turn_count == 1:
            opener = (
                f"Client message: {user_input}\n\n"
                "Greet them warmly as Alex and ask your first question to understand their research need."
            )
            result = await self.run(opener)
        else:
            result = await self.run(user_input)

        return result.text

    def to_dict(self) -> Dict:
        """Serialisable state for API responses."""
        return {
            "brief_saved": self.brief_saved,
            "turn_count": self._turn_count,
            "brief": self.collected_brief,
        }
