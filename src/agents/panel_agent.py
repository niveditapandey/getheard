"""
PanelAgent — Recruits and validates research panels.

Two modes:
  Mode A — Client uploads a CSV of contacts → validate, match to project, return panel
  Mode B — Search internal respondent DB by criteria → rank matches, return panel

Either way, the agent presents a shortlist to the client for confirmation before
interviews are triggered.

Usage:
    agent = PanelAgent(project)
    panel = await agent.build_panel_from_csv(csv_text)   # Mode A
    panel = await agent.query_panel(criteria)             # Mode B
"""

import csv
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import settings
from src.storage.respondent_store import (
    enroll_respondent, search_respondents, update_respondent_status,
    get_respondent, _clean_phone
)
from .base_agent import BaseAgent, ToolSpec

logger = logging.getLogger(__name__)

BASE_DIR  = Path(__file__).parent.parent.parent
PANELS_DIR = BASE_DIR / "panels"
PANELS_DIR.mkdir(exist_ok=True)


PANEL_SYSTEM_PROMPT = """You are a research panel coordinator at GetHeard.

Your job: given a research project brief and either a CSV list or a database query result,
select and validate the best-fit respondents for the study.

Rules:
• Each respondent must match the project's language and target audience
• Flag anyone who has been interviewed in the last 30 days (over-research risk)
• Flag duplicate phone numbers
• If CSV is provided, validate required fields (name, phone, language)
• Provide a coverage assessment: does the panel represent the target audience well?
• Always confirm panel diversity — don't pick all same-city or all same-age respondents
• Return a clear summary the client can review before confirming"""


class PanelAgent(BaseAgent):
    """
    Recruits respondent panels for research projects.

    Attributes:
        final_panel: available after build_panel_from_csv() or query_panel()
    """

    def __init__(self, project: Dict):
        super().__init__()
        self.name = "PanelAgent"
        self.model = settings.gemini_model  # flash — mostly validation logic, not deep reasoning
        self.system_prompt = PANEL_SYSTEM_PROMPT
        self.project = project
        self.project_id = project.get("project_id", "")
        self.final_panel: Optional[Dict] = None
        self._validated: List[Dict] = []
        self._rejected:  List[Dict] = []

        self._register_tools()

    def _register_tools(self):
        self.register_tool(ToolSpec(
            name="validate_respondent",
            description=(
                "Validate a single respondent's details. "
                "Call for each respondent in a CSV or DB result. "
                "Flags issues without discarding the respondent."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "respondent_id": {"type": "string", "description": "ID if from DB, or temp ID for CSV"},
                    "name":     {"type": "string"},
                    "phone":    {"type": "string"},
                    "language": {"type": "string"},
                    "city":     {"type": "string"},
                    "age_range":{"type": "string"},
                    "fit_score":{"type": "integer", "description": "0-10 match score for this project"},
                    "flags":    {"type": "array", "items": {"type": "string"},
                                 "description": "Issues found e.g. 'recently_interviewed', 'language_mismatch'"},
                    "include":  {"type": "boolean", "description": "Whether to include in final panel"},
                },
                "required": ["name", "phone", "language", "fit_score", "include"],
            },
            handler=self._validate_handler,
        ))

        self.register_tool(ToolSpec(
            name="save_panel",
            description="Save the validated panel and generate the client-facing summary.",
            parameters={
                "type": "object",
                "properties": {
                    "panel_name":     {"type": "string"},
                    "total_selected": {"type": "integer"},
                    "coverage_notes": {"type": "string",
                                       "description": "Assessment of how well panel covers the target audience"},
                    "diversity_score":{"type": "string", "enum": ["high","medium","low"]},
                    "client_message": {"type": "string",
                                       "description": "Message to show client before they confirm the panel"},
                    "warnings":       {"type": "array", "items": {"type": "string"}},
                },
                "required": ["total_selected", "coverage_notes", "diversity_score", "client_message"],
            },
            handler=self._save_panel_handler,
        ))

    # ── Handlers ─────────────────────────────────────────────────────────────

    async def _validate_handler(self, **kwargs) -> Dict:
        if kwargs.get("include"):
            self._validated.append(kwargs)
        else:
            self._rejected.append(kwargs)
        return {"status": "recorded", "include": kwargs.get("include")}

    async def _save_panel_handler(
        self,
        total_selected: int,
        coverage_notes: str,
        diversity_score: str,
        client_message: str,
        panel_name: str = "",
        warnings: Optional[List[str]] = None,
    ) -> Dict:
        panel_id = str(uuid.uuid4())[:8]
        self.final_panel = {
            "panel_id":       panel_id,
            "project_id":     self.project_id,
            "panel_name":     panel_name or f"Panel for {self.project.get('name','')}",
            "status":         "pending_confirmation",
            "respondents":    self._validated,
            "rejected":       self._rejected,
            "total_selected": total_selected,
            "total_rejected": len(self._rejected),
            "coverage_notes": coverage_notes,
            "diversity_score": diversity_score,
            "client_message": client_message,
            "warnings":       warnings or [],
            "created_at":     datetime.now(timezone.utc).isoformat(),
            "created_by":     "PanelAgent",
        }
        path = PANELS_DIR / f"{panel_id}.json"
        path.write_text(json.dumps(self.final_panel, indent=2, ensure_ascii=False))
        logger.info(f"[PanelAgent] Panel saved: {panel_id} ({total_selected} selected)")
        return {"status": "saved", "panel_id": panel_id}

    # ── Public interface ──────────────────────────────────────────────────────

    async def build_panel_from_csv(self, csv_text: str) -> Dict:
        """Mode A — validate a client-uploaded CSV and build a panel."""
        rows = self._parse_csv(csv_text)
        n = len(rows)
        rows_summary = "\n".join(
            f"{i+1}. {r.get('name','?')} | {r.get('phone','?')} | "
            f"lang={r.get('language','?')} | city={r.get('city','?')} | age={r.get('age_range','?')}"
            for i, r in enumerate(rows[:50])  # cap at 50 for prompt size
        )
        prompt = (
            f"Project: {self.project.get('name')}\n"
            f"Research type: {self.project.get('research_type')}\n"
            f"Target audience: {self.project.get('audience') or self.project.get('target_audience','')}\n"
            f"Language: {self.project.get('language','en')}\n\n"
            f"Client uploaded {n} contacts:\n{rows_summary}\n\n"
            "Call validate_respondent() for each contact (check fit, flag issues). "
            "Then call save_panel() with a coverage summary and client-facing message."
        )
        await self.run(prompt)
        # Also save any valid CSV rows to the respondent DB
        for row in rows:
            try:
                row["source"] = "csv_upload"
                row["consent_contact"] = True  # client has obtained consent by uploading
                enroll_respondent(row)
            except Exception:
                pass
        return self.final_panel or {}

    async def query_panel(self, criteria: Optional[Dict] = None) -> Dict:
        """Mode B — search respondent DB by criteria and build a panel."""
        criteria = criteria or {}
        criteria.setdefault("language", self.project.get("language", "en"))
        criteria.setdefault("not_interviewed_days", 30)

        matched = search_respondents(criteria)
        n = len(matched)
        matches_summary = "\n".join(
            f"{i+1}. {r.get('name','?')} | {r.get('phone','?')[:8]}*** | "
            f"lang={r.get('language','?')} | city={r.get('city','?')} | "
            f"age={r.get('age_range','?')} | gender={r.get('gender','?')} | "
            f"interests={r.get('interests',[])} | "
            f"interviews_done={r.get('interviews_completed',0)}"
            for i, r in enumerate(matched[:50])
        )
        prompt = (
            f"Project: {self.project.get('name')}\n"
            f"Research type: {self.project.get('research_type')}\n"
            f"Target audience: {self.project.get('audience') or self.project.get('target_audience','')}\n"
            f"Language: {self.project.get('language','en')}\n\n"
            f"Found {n} respondents in DB matching criteria:\n"
            + (matches_summary if matched else "(no matches found)") + "\n\n"
            "Call validate_respondent() for each (max 20 best fits). "
            "Score each for fit, flag over-researched respondents. "
            "Then call save_panel() with a diversity assessment and client message. "
            "If fewer than 5 matches exist, note this clearly in warnings."
        )
        await self.run(prompt)
        return self.final_panel or {}

    def confirm_panel(self, panel_id: str) -> bool:
        """Client confirmed — update respondent statuses to 'scheduled'."""
        path = PANELS_DIR / f"{panel_id}.json"
        if not path.exists():
            return False
        panel = json.loads(path.read_text(encoding="utf-8"))
        panel["status"] = "confirmed"
        panel["confirmed_at"] = datetime.now(timezone.utc).isoformat()
        for r in panel.get("respondents", []):
            rid = r.get("respondent_id")
            if rid:
                update_respondent_status(rid, "scheduled")
        path.write_text(json.dumps(panel, indent=2, ensure_ascii=False))
        logger.info(f"[PanelAgent] Panel confirmed: {panel_id}")
        return True

    # ── CSV parser ────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_csv(csv_text: str) -> List[Dict]:
        """Parse CSV with flexible header matching."""
        ALIASES = {
            "name":       ["name", "full_name", "respondent_name", "participant"],
            "phone":      ["phone", "mobile", "phone_number", "mobile_number", "contact"],
            "language":   ["language", "lang", "language_code"],
            "email":      ["email", "email_address", "mail"],
            "city":       ["city", "location", "town"],
            "age_range":  ["age_range", "age", "age_group"],
            "gender":     ["gender", "sex"],
            "whatsapp_number": ["whatsapp", "whatsapp_number", "wa"],
        }
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        headers = {h.strip().lower(): h for h in (reader.fieldnames or [])}

        def find_col(field):
            for alias in ALIASES.get(field, [field]):
                if alias in headers:
                    return headers[alias]
            return None

        col_map = {f: find_col(f) for f in ALIASES}
        rows = []
        for raw_row in reader:
            row = {}
            for field, col in col_map.items():
                if col and raw_row.get(col, "").strip():
                    row[field] = raw_row[col].strip()
            if row.get("name") and row.get("phone"):
                rows.append(row)
        return rows
