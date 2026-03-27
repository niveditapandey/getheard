"""
InterviewAgent — Contextual interview conductor.

Unlike the state machine in GeminiInterviewer (which advances after exactly
2 follow-ups regardless of answer quality), this agent:

  - Reads the answer and DECIDES whether to probe or advance
  - Generates context-aware follow-ups (not just the preset probe)
  - Can empathize before probing emotional topics
  - Skips questions if the respondent already answered them
  - Closes naturally when all questions are covered

The agent uses its decide_next() tool to log its reasoning, enabling
audit of why it made each interviewing decision.

Usage:
    agent = InterviewAgent(questions, language="en", research_type="cx", objective="...")
    opening = agent.get_opening()  # returns text of first question

    # In voice pipeline loop:
    response_text, is_done = await agent.process_response("respondent said this")
"""

import logging
from typing import Dict, List, Optional, Tuple

from config.settings import settings
from .base_agent import BaseAgent, ToolSpec

logger = logging.getLogger(__name__)

INTERVIEW_SYSTEM_PROMPT = """You are Alex, a skilled qualitative research interviewer.

You are conducting a {research_type} interview in {language_name}.

Research Objective: {objective}

Current question you are exploring:
  Main: {current_main}
  Probe: {current_probe}
  Intent: {current_intent}

Follow-ups given so far on this question: {followup_count}
Questions remaining after current: {remaining}

━━ YOUR JOB ━━
Read the respondent's latest answer and decide what to do next.
You MUST call decide_next() with your decision.

━━ DECISION GUIDE ━━

PROBE when:
  • Answer is vague, surface-level, or under 2 sentences
  • An interesting point was raised but not explored
  • You haven't yet used the preset probe
  • The respondent described a problem but didn't explain it

ADVANCE when:
  • You have a rich, detailed answer
  • The respondent has already answered 2–3 follow-ups on this question
  • The respondent is repeating themselves
  • The answer already covers the question's intent thoroughly

EMPATHIZE_THEN_PROBE when:
  • The respondent shared something emotional, stressful, or difficult
  • (Acknowledge their feeling first, then gently probe)

CLOSE when:
  • This was the last question AND the answer is complete

━━ RESPONSE RULES ━━
• Speak in {language_name} — match the respondent's language
• Be warm, curious, and human — never robotic
• Never make the respondent feel interrogated
• Keep your response conversational (1–2 sentences maximum)"""


class InterviewAgent(BaseAgent):
    """
    Decision-making layer for conducting research interviews.

    Wraps the question list and uses Gemini to decide whether to probe,
    advance, empathize, or close — based on the actual answer quality.
    """

    LANGUAGE_NAMES = {
        "en": "English", "hi": "Hindi", "id": "Indonesian",
        "fil": "Filipino", "th": "Thai", "vi": "Vietnamese",
        "ko": "Korean", "ja": "Japanese", "zh": "Mandarin",
    }

    def __init__(
        self,
        questions: List[Dict],
        language: str = "en",
        research_type: str = "cx",
        objective: str = "",
    ):
        super().__init__()
        self.name = "InterviewAgent"
        self.model = settings.gemini_model  # flash — real-time probe decisions, latency critical
        self.questions = questions
        self.language = language
        self.research_type = research_type
        self.objective = objective

        self.current_q_idx: int = 0
        self.followup_count: int = 0
        self.is_complete: bool = False
        self.conversation: List[Dict] = []
        self.decision_log: List[Dict] = []  # audit trail

        self._next_action: Optional[str] = None
        self._next_text: Optional[str] = None

        self.register_tool(ToolSpec(
            name="decide_next",
            description=(
                "State your interviewing decision and what to say next to the respondent. "
                "Always call this — it is how you communicate your turn."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["probe", "advance", "empathize_then_probe", "close"],
                        "description": "The interviewing action to take",
                    },
                    "response_text": {
                        "type": "string",
                        "description": "What to say to the respondent (in the interview language)",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Internal note explaining why you chose this action",
                    },
                },
                "required": ["action", "response_text", "reasoning"],
            },
            handler=self._decide_next_handler,
        ))

        self._update_system_prompt()

    # ── Prompt management ────────────────────────────────────────────────────

    def _current_question(self) -> Dict:
        if self.current_q_idx < len(self.questions):
            return self.questions[self.current_q_idx]
        return {"main": "", "probe": "", "intent": "closing"}

    def _update_system_prompt(self):
        q = self._current_question()
        self.system_prompt = INTERVIEW_SYSTEM_PROMPT.format(
            research_type=self.research_type,
            language_name=self.LANGUAGE_NAMES.get(self.language, self.language),
            objective=self.objective or "Understand the respondent's experience",
            current_main=q.get("main", ""),
            current_probe=q.get("probe", ""),
            current_intent=q.get("intent", ""),
            followup_count=self.followup_count,
            remaining=max(0, len(self.questions) - self.current_q_idx - 1),
        )
        self._initialized = False  # trigger re-init with new prompt

    # ── Tool handlers ────────────────────────────────────────────────────────

    async def _decide_next_handler(
        self, action: str, response_text: str, reasoning: str
    ) -> Dict:
        self._next_action = action
        self._next_text = response_text
        self.decision_log.append({
            "q_idx": self.current_q_idx,
            "followup_count": self.followup_count,
            "action": action,
            "reasoning": reasoning,
        })
        logger.info(
            f"[InterviewAgent] Q{self.current_q_idx + 1} | "
            f"action={action} | {reasoning[:70]}"
        )
        return {"status": "decision_recorded", "action": action}

    # ── Public interface ─────────────────────────────────────────────────────

    def get_opening(self) -> str:
        """Return the first question text and record it in conversation."""
        if not self.questions:
            return "Could you start by telling me a little about yourself?"
        text = self.questions[0]["main"]
        self.conversation.append({"speaker": "interviewer", "text": text})
        return text

    async def process_response(self, respondent_text: str) -> Tuple[str, bool]:
        """
        Process the respondent's latest answer and return the next interviewer turn.

        Returns:
            (response_text, is_complete)
        """
        self.conversation.append({"speaker": "respondent", "text": respondent_text})

        # Build recent context (last 6 turns = 3 exchanges)
        recent = self.conversation[-6:]
        context_lines = []
        for turn in recent:
            speaker = "Interviewer" if turn["speaker"] == "interviewer" else "Respondent"
            context_lines.append(f"{speaker}: {turn['text']}")
        context = "\n".join(context_lines)

        prompt = f"""Recent conversation:
{context}

The respondent just said:
"{respondent_text}"

Follow-up count on current question: {self.followup_count}
Questions remaining: {max(0, len(self.questions) - self.current_q_idx - 1)}

What do you do next? Call decide_next()."""

        # Reset decision state and run
        self._next_action = None
        self._next_text = None
        self._update_system_prompt()
        await self.run(prompt)

        action = self._next_action or "advance"
        text = self._next_text or self._fallback_next_text()

        # Apply the decision
        if action == "advance":
            self.current_q_idx += 1
            self.followup_count = 0
            self._update_system_prompt()
            if self.current_q_idx >= len(self.questions):
                action = "close"

        if action == "close":
            self.is_complete = True
        elif action in ("probe", "empathize_then_probe"):
            self.followup_count += 1

        self.conversation.append({"speaker": "interviewer", "text": text})
        return text, self.is_complete

    def _fallback_next_text(self) -> str:
        """Fallback if agent didn't call decide_next."""
        q = self._current_question()
        return q.get("main", "Thank you — that's really helpful to know.")
