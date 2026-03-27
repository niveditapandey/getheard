"""
PricingAgent — Presents quote after brief, negotiates via 3 levers.

After BriefAgent completes, PricingAgent:
1. Computes the initial quote from project parameters
2. Presents it to the client with 3 adjustment levers
3. Handles respondent incentive add-on
4. Passes confirmed quote to TimelineAgent
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional

from config.settings import settings
from src.storage.pricing_store import compute_quote, load_pricing_config
from .base_agent import BaseAgent, ToolSpec

logger = logging.getLogger(__name__)

PRICING_SYSTEM_PROMPT = """You are GetHeard's pricing specialist.

Your job: after a research brief is confirmed, present a transparent quote and help the client optimise it.

Rules:
- Always show an itemised breakdown (study fee, recruitment, incentive, urgency if selected)
- Explain what each line item means in plain language
- When client adjusts panel size, panel source, or study type — recompute and show updated total
- If client adds respondent incentive, explain: "Higher incentive = faster recruitment + better response rates"
- If client wants faster delivery, add the urgency premium (25%) and explain the trade-off
- Be helpful, not pushy — if they want a lower price, show them how to get it
- Always end with: "Does this look right? Say 'confirm' when you're ready to pay."
- Currency: INR (₹). Always show amounts with ₹ symbol and comma formatting (₹22,800)
- Never make up prices — always use the compute_price tool"""

class PricingAgent(BaseAgent):
    def __init__(self, project: Dict, client: Optional[Dict] = None):
        super().__init__()
        self.name = "PricingAgent"
        self.model = settings.gemini_model
        self.system_prompt = PRICING_SYSTEM_PROMPT
        self.project = project
        self.client = client or {}
        self.confirmed_quote: Optional[Dict] = None
        self._register_tools()

    def _register_tools(self):
        self.register_tool(ToolSpec(
            name="compute_price",
            description="Compute or recompute the quote. Call whenever any lever changes.",
            parameters={
                "type": "object",
                "properties": {
                    "study_type":   {"type": "string", "enum": ["nps_csat","feature_feedback","pain_points","custom"]},
                    "panel_size":   {"type": "integer", "description": "Number of respondents"},
                    "panel_source": {"type": "string", "enum": ["csv","db","targeted"]},
                    "market":       {"type": "string", "description": "Country code e.g. IN, SG"},
                    "industry":     {"type": "string", "description": "Industry for targeted recruitment multiplier"},
                    "urgency":      {"type": "boolean", "description": "Client wants expedited delivery (+25%)"},
                    "respondent_incentive_per_head": {"type": "integer", "description": "Extra INR per respondent client adds as incentive"},
                },
                "required": ["study_type", "panel_size", "panel_source"],
            },
            handler=self._compute_price_handler,
        ))

        self.register_tool(ToolSpec(
            name="confirm_quote",
            description="Client has confirmed the quote. Save it and trigger payment flow.",
            parameters={
                "type": "object",
                "properties": {
                    "quote": {"type": "object", "description": "The final quote dict from compute_price"},
                    "urgency": {"type": "boolean"},
                    "respondent_incentive_per_head": {"type": "integer"},
                    "panel_size": {"type": "integer"},
                    "panel_source": {"type": "string"},
                },
                "required": ["quote", "panel_size", "panel_source"],
            },
            handler=self._confirm_quote_handler,
        ))

    async def _compute_price_handler(self, **kwargs) -> Dict:
        quote = compute_quote(
            study_type=kwargs.get("study_type", "custom"),
            panel_size=int(kwargs.get("panel_size", 10)),
            panel_source=kwargs.get("panel_source", "csv"),
            market=kwargs.get("market", self.project.get("market", "IN")),
            industry=kwargs.get("industry", self.project.get("industry", "other")),
            urgency=bool(kwargs.get("urgency", False)),
            respondent_incentive_per_head=int(kwargs.get("respondent_incentive_per_head", 0)),
        )
        return quote

    async def _confirm_quote_handler(self, quote: Dict, panel_size: int, panel_source: str,
                                      urgency: bool = False, respondent_incentive_per_head: int = 0, **kwargs) -> Dict:
        self.confirmed_quote = {
            **quote,
            "panel_size": panel_size,
            "panel_source": panel_source,
            "urgency": urgency,
            "respondent_incentive_per_head": respondent_incentive_per_head,
            "status": "awaiting_payment",
        }
        logger.info(f"[PricingAgent] Quote confirmed: ₹{quote.get('total',0):,}")
        return {"status": "confirmed", "total": quote.get("total", 0), "ready_for_payment": True}

    async def present_quote(self) -> Dict:
        """Initial quote presentation after brief is complete."""
        # Derive study_type from project
        rt = self.project.get("research_type", "custom")
        study_type_map = {
            "nps": "nps_csat", "csat": "nps_csat",
            "feature": "feature_feedback", "product": "feature_feedback",
            "pain": "pain_points", "cx": "pain_points",
            "custom": "custom",
        }
        study_type = "custom"
        for k, v in study_type_map.items():
            if k in rt.lower():
                study_type = v
                break

        panel_size = self.project.get("target_respondents", 10)
        market = self.project.get("market", "IN")
        industry = self.project.get("industry", "other")

        initial_quote = compute_quote(
            study_type=study_type,
            panel_size=panel_size,
            panel_source="csv",  # default — client can switch
            market=market,
            industry=industry,
        )

        prompt = (
            f"Project: {self.project.get('name')}\n"
            f"Type: {study_type}\n"
            f"Target respondents: {panel_size}\n"
            f"Market: {market}\n"
            f"Industry: {industry}\n\n"
            f"Initial quote computed:\n{json.dumps(initial_quote, indent=2)}\n\n"
            "Present this quote to the client clearly with itemised breakdown.\n"
            "Explain the 3 levers they can adjust:\n"
            "  1. Panel size (more/fewer respondents)\n"
            "  2. Panel source (CSV=cheapest, GetHeard DB=faster, Targeted=premium)\n"
            "  3. Study type (template=cheaper, custom=more expensive)\n"
            "Also offer: respondent incentive top-up and urgency option.\n"
            "Use compute_price tool if they want to adjust anything.\n"
            "Use confirm_quote tool when they say 'confirm' or 'proceed'."
        )
        await self.run(prompt)
        return self.confirmed_quote or {}
