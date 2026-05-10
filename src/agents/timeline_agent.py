"""
TimelineAgent — Estimates delivery timeline after quote is confirmed.

Factors:
- Panel size (more respondents = more days)
- Panel source (targeted takes longer to recruit)
- Geography (some markets harder to schedule)
- Study complexity (question count, interview duration)
- Urgency flag (already paid for via pricing)
"""
import logging
from typing import Dict, Optional

from config.settings import settings
from .base_agent import BaseAgent, ToolSpec

logger = logging.getLogger(__name__)

TIMELINE_SYSTEM_PROMPT = """You are GetHeard's project timeline estimator.

After a client confirms their quote, you calculate a realistic delivery estimate.

Rules:
- Be honest. Don't over-promise.
- Break down the timeline into phases: Recruitment, Scheduling, Interviews, Analysis, Report
- If urgency premium was paid, compress timeline by ~30% where possible
- Give a range (e.g. "5–7 business days") not a single number
- If market is JP/KR/CN, add 1–2 days for scheduling complexity
- Always end with the estimated report delivery date (calculate from today)
- Use the set_timeline tool to record the official estimate"""

class TimelineAgent(BaseAgent):
    def __init__(self, project: Dict, quote: Dict):
        super().__init__()
        self.name = "TimelineAgent"
        self.model = settings.gemini_model
        self.system_prompt = TIMELINE_SYSTEM_PROMPT
        self.project = project
        self.quote = quote
        self.timeline: Optional[Dict] = None
        self._register_tools()

    def _register_tools(self):
        self.register_tool(ToolSpec(
            name="set_timeline",
            description="Record the official timeline estimate.",
            parameters={
                "type": "object",
                "properties": {
                    "recruitment_days":  {"type": "integer"},
                    "scheduling_days":   {"type": "integer"},
                    "interview_days":    {"type": "integer"},
                    "analysis_days":     {"type": "integer"},
                    "total_min_days":    {"type": "integer"},
                    "total_max_days":    {"type": "integer"},
                    "estimated_report_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                    "client_message":    {"type": "string", "description": "Plain-English message to show client"},
                    "caveats":           {"type": "array", "items": {"type": "string"}},
                },
                "required": ["total_min_days", "total_max_days", "estimated_report_date", "client_message"],
            },
            handler=self._set_timeline_handler,
        ))

    async def _set_timeline_handler(self, **kwargs) -> Dict:
        self.timeline = kwargs
        logger.info(f"[TimelineAgent] Timeline set: {kwargs.get('total_min_days')}–{kwargs.get('total_max_days')} days")
        return {"status": "set", "timeline": self.timeline}

    async def estimate(self) -> Dict:
        """Generate timeline estimate for this project + quote."""
        from datetime import date
        today = date.today().isoformat()
        prompt = (
            f"Today: {today}\n"
            f"Project: {self.project.get('name')}\n"
            f"Market: {self.project.get('market','IN')}\n"
            f"Panel size: {self.quote.get('panel_size', 10)} respondents\n"
            f"Panel source: {self.quote.get('panel_source','csv')}\n"
            f"Urgency delivery requested: {self.quote.get('urgency', False)}\n"
            f"Question count: {len(self.project.get('questions',[]))}\n\n"
            "Estimate the delivery timeline phase by phase.\n"
            "Call set_timeline with your estimate."
        )
        await self.run(prompt)
        return self.timeline or {}
