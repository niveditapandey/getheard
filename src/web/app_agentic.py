"""
app_agentic.py — Agentic routes as an APIRouter.

Included into app.py so all routes are served on port 8000.
Can also run standalone on port 8001:
    uvicorn src.web.app_agentic:standalone_app --port 8001 --reload

Routes (all prefixed /agent):
  GET  /agent                        → agentic home page
  GET  /agent/brief                  → brief chat UI

  POST /agent/api/brief/start        → create BriefAgent session
  POST /agent/api/brief/message      → send message to BriefAgent
  GET  /agent/api/brief/{id}         → session state

  POST /agent/api/design             → run DesignerAgent on a brief
  GET  /agent/api/projects           → list projects
  GET  /agent/api/projects/{id}      → project detail

  POST /agent/api/reports/generate   → run 4-pass AnalysisAgent
  GET  /agent/api/reports            → list reports
  GET  /agent/api/reports/{id}       → full report JSON
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.orchestrator import orchestrator

logger = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).parent.parent.parent
PROJECTS_DIR  = BASE_DIR / "projects"
REPORTS_DIR   = BASE_DIR / "reports"
TEMPLATES_DIR = BASE_DIR / "src" / "web" / "templates"

def _html(name: str) -> HTMLResponse:
    f = TEMPLATES_DIR / name
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else f"<h1>{name} not found</h1>")

# ── Router (included in app.py) ──────────────────────────────────────────────
router = APIRouter(prefix="/agent", tags=["agentic"])


# ── Request models ───────────────────────────────────────────────────────────

class BriefMessageRequest(BaseModel):
    session_id: str
    message: str

class DesignRequest(BaseModel):
    brief: Dict

class ReportRequest(BaseModel):
    project_id: str
    transcript_files: Optional[List[str]] = None


# ── UI pages ─────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def agent_home():
    return _html("agent/index.html")

@router.get("/brief", response_class=HTMLResponse)
async def brief_page():
    return _html("agent/brief_chat.html")


# ── Brief API ────────────────────────────────────────────────────────────────

@router.post("/api/brief/start")
async def start_brief_session():
    session_id = orchestrator.start_brief_session()
    return {"session_id": session_id}

@router.post("/api/brief/message")
async def brief_message(req: BriefMessageRequest):
    try:
        result = await orchestrator.send_brief_message(req.session_id, req.message)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        detail = str(exc)
        if "GEMINI_API_KEY" in detail or "Publisher Model" in detail or "NOT_FOUND" in detail:
            detail = "Gemini API not configured. Add GEMINI_API_KEY to your .env file. Get a free key at https://aistudio.google.com/app/apikey"
        logger.error(f"Brief message error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=detail)

@router.get("/api/brief/{session_id}")
async def get_brief_state(session_id: str):
    return {
        "session_id": session_id,
        "is_complete": orchestrator.is_brief_complete(session_id),
        "brief": orchestrator.get_brief(session_id),
    }


# ── Design API ───────────────────────────────────────────────────────────────

@router.post("/api/design")
async def design_study(req: DesignRequest):
    try:
        project = await orchestrator.design_study(req.brief)
        return project
    except Exception as exc:
        logger.error(f"Design error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Projects API ─────────────────────────────────────────────────────────────

@router.get("/api/projects")
async def list_agentic_projects():
    projects = []
    for p in sorted(PROJECTS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            data = json.loads(p.read_text())
            projects.append({
                "project_id":    data.get("project_id"),
                "name":          data.get("name"),
                "research_type": data.get("research_type"),
                "language":      data.get("language"),
                "question_count": len(data.get("questions", [])),
                "session_count":  len(data.get("sessions", [])),
                "created_at":    data.get("created_at"),
                "created_by":    data.get("created_by", "manual"),
            })
        except Exception:
            pass
    return {"projects": projects}

@router.get("/api/projects/{project_id}")
async def get_agentic_project(project_id: str):
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    return json.loads(path.read_text())


# ── Reports API ──────────────────────────────────────────────────────────────

@router.post("/api/reports/generate")
async def generate_agentic_report(req: ReportRequest):
    try:
        report = await orchestrator.generate_report(
            project_id=req.project_id,
            transcript_files=req.transcript_files,
        )
        return {
            "report_id":         report["report_id"],
            "project_name":      report.get("project_name"),
            "total_transcripts": report.get("total_transcripts"),
            "overall_sentiment": report.get("overall_sentiment"),
            "report_quality":    report.get("report_quality"),
            "theme_count":       len(report.get("key_themes", [])),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Report error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/api/reports")
async def list_agentic_reports():
    reports = []
    for p in sorted(REPORTS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            data = json.loads(p.read_text())
            reports.append({
                "report_id":         data.get("report_id"),
                "project_name":      data.get("project_name"),
                "total_transcripts": data.get("total_transcripts"),
                "overall_sentiment": data.get("overall_sentiment"),
                "report_quality":    data.get("report_quality"),
                "generated_at":      data.get("generated_at"),
                "generated_by":      data.get("generated_by", "one-shot"),
            })
        except Exception:
            pass
    return {"reports": reports}

@router.get("/api/reports/{report_id}")
async def get_agentic_report(report_id: str):
    path = REPORTS_DIR / f"{report_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return json.loads(path.read_text())


# ── Standalone app (port 8001) ───────────────────────────────────────────────
standalone_app = FastAPI(title="GetHeard Agentic", version="2.0.0")
standalone_app.include_router(router)
