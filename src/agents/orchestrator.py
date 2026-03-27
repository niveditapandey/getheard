"""
Orchestrator — Coordinates the full research pipeline.

The Orchestrator wires the four agents together and manages shared state
(projects, transcripts, reports) using the same JSON persistence layer
as the non-agentic version.

Pipeline stages:
  ① Brief       BriefAgent   → collects research brief via conversation
  ② Design      DesignerAgent → generates and self-reviews questions
  ③ Interview   InterviewAgent (per session, managed by VoiceInterviewPipeline)
  ④ Analysis    AnalysisAgent → 4-pass report generation

Each stage can be run independently (e.g., skip brief if project already exists,
or run analysis on demand after N interviews are complete).
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .brief_agent import BriefAgent
from .designer_agent import DesignerAgent
from .analysis_agent import AnalysisAgent
from .interview_agent import InterviewAgent

logger = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).parent.parent.parent
PROJECTS_DIR = BASE_DIR / "projects"
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"
REPORTS_DIR  = BASE_DIR / "reports"

for _d in (PROJECTS_DIR, TRANSCRIPTS_DIR, REPORTS_DIR):
    _d.mkdir(exist_ok=True)


# ── Session registry ─────────────────────────────────────────────────────────
# In-memory registry of active BriefAgent chat sessions.
# Key: session_id (str), Value: BriefAgent instance
_brief_sessions: Dict[str, BriefAgent] = {}


class Orchestrator:
    """
    High-level coordinator for the GetHeard agentic research pipeline.

    Usage patterns:

      # Start a new brief session (conversational)
      session_id = orchestrator.start_brief_session()
      reply = await orchestrator.send_brief_message(session_id, "We want to understand churn")
      # ... repeat until orchestrator.is_brief_complete(session_id)
      brief = orchestrator.get_brief(session_id)

      # Design the study
      project = await orchestrator.design_study(brief)

      # Analysis (after interviews are recorded)
      report = await orchestrator.generate_report(project_id)
    """

    def __init__(self):
        pass

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage ① — Brief Collection
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def start_brief_session(self) -> str:
        """Create a new BriefAgent session and return the session ID."""
        session_id = str(uuid.uuid4())[:8]
        _brief_sessions[session_id] = BriefAgent()
        logger.info(f"[Orchestrator] Brief session started: {session_id}")
        return session_id

    async def send_brief_message(self, session_id: str, user_message: str) -> Dict:
        """
        Forward a user message to the BriefAgent session.

        Returns:
            {
                "reply": str,          agent's conversational response
                "brief_saved": bool,   True when brief is complete
                "brief": dict | None,  the collected brief (when saved)
            }
        """
        agent = _brief_sessions.get(session_id)
        if not agent:
            return {"error": f"No brief session found: {session_id}"}

        reply = await agent.message(user_message)
        return {
            "reply": reply,
            "brief_saved": agent.brief_saved,
            "brief": agent.collected_brief,
        }

    def get_brief(self, session_id: str) -> Optional[Dict]:
        """Return the collected brief for a session (None if not yet complete)."""
        agent = _brief_sessions.get(session_id)
        return agent.collected_brief if agent else None

    def is_brief_complete(self, session_id: str) -> bool:
        agent = _brief_sessions.get(session_id)
        return bool(agent and agent.brief_saved)

    def cleanup_brief_session(self, session_id: str):
        _brief_sessions.pop(session_id, None)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage ② — Study Design
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def design_study(self, brief: Dict) -> Dict:
        """
        Run DesignerAgent on a research brief and persist the resulting project.

        Returns the saved project dict (same format as non-agentic projects).
        """
        logger.info(f"[Orchestrator] Designing study: {brief.get('project_name')}")

        agent = DesignerAgent(brief)
        questions = await agent.design()

        project_id = str(uuid.uuid4())[:8]
        project = {
            "project_id":    project_id,
            "name":          brief.get("project_name", "Untitled"),
            "research_type": brief.get("research_type", "cx"),
            "industry":      brief.get("industry", ""),
            "objective":     brief.get("objective", ""),
            "audience":      brief.get("target_audience", brief.get("audience", "")),
            "language":      brief.get("language", "en"),
            "topics":        brief.get("topics", []),
            "question_count": len(questions),
            "questions":     questions,
            "sessions":      [],
            "created_at":    datetime.now(timezone.utc).isoformat(),
            "created_by":    "DesignerAgent",
            "design_metadata": {
                "review_passes":  len(agent.review_history),
                "issues_found":   sum(len(r["issues"]) for r in agent.review_history),
                "quality_summary": agent._finalize_summary,
            },
        }

        path = PROJECTS_DIR / f"{project_id}.json"
        path.write_text(json.dumps(project, indent=2, ensure_ascii=False))
        logger.info(
            f"[Orchestrator] Project saved: {project_id} "
            f"({len(questions)} questions, {len(agent.review_history)} review passes)"
        )
        return project

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage ③ — Interview (per session)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def create_interview_agent(self, project_id: str) -> Optional[InterviewAgent]:
        """
        Create an InterviewAgent pre-loaded with a project's questions.
        The voice pipeline uses this to drive each interview session.
        """
        path = PROJECTS_DIR / f"{project_id}.json"
        if not path.exists():
            logger.warning(f"[Orchestrator] Project not found: {project_id}")
            return None

        project = json.loads(path.read_text())
        agent = InterviewAgent(
            questions=project.get("questions", []),
            language=project.get("language", "en"),
            research_type=project.get("research_type", "cx"),
            objective=project.get("objective", ""),
        )
        logger.info(
            f"[Orchestrator] InterviewAgent created for project {project_id} "
            f"({len(project.get('questions', []))} questions)"
        )
        return agent

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage ④ — Analysis & Report Generation
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def generate_report(
        self,
        project_id: str,
        transcript_files: Optional[List[str]] = None,
    ) -> Dict:
        """
        Run 4-pass AnalysisAgent on all transcripts linked to a project.

        Args:
            project_id: The project to analyse
            transcript_files: Override list of transcript filenames (optional)

        Returns:
            Saved report dict with report_id included
        """
        # Load project
        proj_path = PROJECTS_DIR / f"{project_id}.json"
        if not proj_path.exists():
            raise ValueError(f"Project not found: {project_id}")
        project = json.loads(proj_path.read_text())

        # Load transcripts
        if transcript_files:
            transcript_paths = [TRANSCRIPTS_DIR / f for f in transcript_files]
        else:
            # Find transcripts linked via project.sessions
            session_ids = set(project.get("sessions", []))
            transcript_paths = []
            for p in TRANSCRIPTS_DIR.glob("*.json"):
                try:
                    t = json.loads(p.read_text())
                    if t.get("session_id") in session_ids or t.get("metadata", {}).get("project_id") == project_id:
                        transcript_paths.append(p)
                except Exception:
                    pass

        if not transcript_paths:
            raise ValueError("No transcripts found for this project")

        transcripts = []
        for tp in transcript_paths:
            try:
                transcripts.append(json.loads(tp.read_text()))
            except Exception as exc:
                logger.warning(f"[Orchestrator] Could not load transcript {tp}: {exc}")

        logger.info(
            f"[Orchestrator] Analysing {len(transcripts)} transcripts "
            f"for project {project_id}"
        )

        # Run AnalysisAgent
        agent = AnalysisAgent(
            transcripts=transcripts,
            project_name=project["name"],
            research_type=project.get("research_type", "cx"),
            objective=project.get("objective", ""),
            questions=project.get("questions", []),
        )
        report = await agent.analyze()

        if not report:
            raise RuntimeError("AnalysisAgent returned an empty report")

        # Persist report
        report_id = str(uuid.uuid4())[:8]
        report["report_id"] = report_id
        report["project_id"] = project_id
        report["generated_at"] = datetime.now(timezone.utc).isoformat()
        report["generated_by"] = "AnalysisAgent"

        report_path = REPORTS_DIR / f"{report_id}.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

        logger.info(f"[Orchestrator] Report saved: {report_id}")
        return report

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Convenience — run full pipeline from brief to project (no interviews)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def run_brief_to_project(self, brief: Dict) -> Dict:
        """
        Convenience method: design → save project from a pre-collected brief.
        Equivalent to design_study() but named for pipeline clarity.
        """
        return await self.design_study(brief)


# Module-level singleton
orchestrator = Orchestrator()
