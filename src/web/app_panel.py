"""
app_panel.py — Panel recruitment routes as an APIRouter.
Mounted in app.py under /panel.

Routes:
  GET  /panel                         → panel home (redirect to dashboard)
  GET  /enroll                        → public respondent enrollment form

  POST /api/respondents/enroll        → enroll a respondent
  GET  /api/respondents               → list respondents (with optional filters)
  GET  /api/respondents/stats         → aggregate counts
  GET  /api/respondents/{id}          → single respondent
  PATCH /api/respondents/{id}/status  → update status

  POST /panel/api/csv-upload          → Mode A: CSV → panel
  POST /panel/api/query               → Mode B: DB search → panel
  GET  /panel/api/{project_id}        → get panel for a project
  POST /panel/api/{panel_id}/confirm  → client confirms panel
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.respondent_store import (
    enroll_respondent, get_respondent, list_respondents,
    update_respondent_status, search_respondents, get_stats
)
from src.agents.panel_agent import PanelAgent

logger = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).parent.parent.parent
PROJECTS_DIR  = BASE_DIR / "projects"
PANELS_DIR    = BASE_DIR / "panels"
TEMPLATES_DIR = BASE_DIR / "src" / "web" / "templates"

router = APIRouter(tags=["panel"])


def _html(name: str) -> HTMLResponse:
    f = TEMPLATES_DIR / name
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else f"<h1>{name} not found</h1>")


def _load_project(project_id: str) -> Dict:
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Project {project_id} not found")
    return json.loads(path.read_text(encoding="utf-8"))


# ── Request models ────────────────────────────────────────────────────────────

class EnrollRequest(BaseModel):
    name: str
    phone: str
    language: str
    consent_contact: bool
    whatsapp_number: Optional[str] = None
    voice_number: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    age_range: Optional[str] = None
    gender: Optional[str] = None
    marital_status: Optional[str] = None
    occupation: Optional[str] = None
    interests: Optional[List[str]] = None
    sexual_orientation: Optional[str] = None
    medical_conditions: Optional[str] = None
    source: Optional[str] = "web_form"


class StatusUpdateRequest(BaseModel):
    status: str


class PanelQueryRequest(BaseModel):
    project_id: str
    target_count: int = 20
    language: Optional[str] = None
    city: Optional[str] = None
    age_range: Optional[str] = None
    gender: Optional[str] = None
    interests: Optional[List[str]] = None
    not_interviewed_days: int = 30


# ── Enrollment form ───────────────────────────────────────────────────────────

@router.get("/enroll", response_class=HTMLResponse)
async def serve_enroll():
    return _html("enroll.html")


# ── Respondent API ────────────────────────────────────────────────────────────

@router.post("/api/respondents/enroll")
async def api_enroll(req: EnrollRequest):
    try:
        respondent = enroll_respondent(req.model_dump(exclude_none=False))
        return {"status": "enrolled", "respondent_id": respondent["respondent_id"], "respondent": respondent}
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        logger.error(f"Enrollment error: {exc}", exc_info=True)
        raise HTTPException(500, str(exc))


@router.get("/api/respondents")
async def api_list_respondents(
    language: Optional[str] = None,
    city: Optional[str] = None,
    age_range: Optional[str] = None,
    gender: Optional[str] = None,
    status: Optional[str] = None,
):
    filters: Dict = {}
    if language: filters["language"] = language
    if city:     filters["city"] = city
    if age_range: filters["age_range"] = age_range
    if gender:   filters["gender"] = gender
    if status:   filters["status"] = status
    respondents = list_respondents(filters or None)
    return {"respondents": respondents, "count": len(respondents)}


@router.get("/api/respondents/stats")
async def api_respondent_stats():
    return get_stats()


@router.get("/api/respondents/{respondent_id}")
async def api_get_respondent(respondent_id: str):
    r = get_respondent(respondent_id)
    if not r:
        raise HTTPException(404, "Respondent not found")
    return r


@router.patch("/api/respondents/{respondent_id}/status")
async def api_update_status(respondent_id: str, req: StatusUpdateRequest):
    ok = update_respondent_status(respondent_id, req.status)
    if not ok:
        raise HTTPException(404, "Respondent not found")
    return {"status": "updated", "new_status": req.status}


# ── Panel API — Mode A (CSV upload) ──────────────────────────────────────────

@router.post("/panel/api/csv-upload")
async def api_csv_upload(
    project_id: str = Form(...),
    file: UploadFile = File(...),
):
    """Mode A — client uploads CSV of respondents for a project."""
    project = _load_project(project_id)
    try:
        csv_bytes = await file.read()
        csv_text = csv_bytes.decode("utf-8-sig")  # handles BOM from Excel
    except Exception as exc:
        raise HTTPException(400, f"Could not read CSV: {exc}")

    try:
        agent = PanelAgent(project)
        panel = await agent.build_panel_from_csv(csv_text)
        if not panel:
            raise HTTPException(500, "PanelAgent returned empty panel")
        return panel
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"CSV panel build error: {exc}", exc_info=True)
        raise HTTPException(500, str(exc))


# ── Panel API — Mode B (DB query) ────────────────────────────────────────────

@router.post("/panel/api/query")
async def api_panel_query(req: PanelQueryRequest):
    """Mode B — search respondent DB and build a panel."""
    project = _load_project(req.project_id)
    criteria = {
        k: v for k, v in {
            "language":             req.language or project.get("language"),
            "city":                 req.city,
            "age_range":            req.age_range,
            "gender":               req.gender,
            "interests":            req.interests,
            "not_interviewed_days": req.not_interviewed_days,
        }.items() if v is not None
    }
    try:
        agent = PanelAgent(project)
        panel = await agent.query_panel(criteria)
        if not panel:
            raise HTTPException(500, "PanelAgent returned empty panel")
        return panel
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Panel query error: {exc}", exc_info=True)
        raise HTTPException(500, str(exc))


# ── Panel management ──────────────────────────────────────────────────────────

@router.get("/panel/api/{project_id}")
async def api_get_panel(project_id: str):
    """Get most recent panel for a project."""
    panels = []
    for p in PANELS_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("project_id") == project_id:
                panels.append(data)
        except Exception:
            pass
    if not panels:
        raise HTTPException(404, "No panel found for this project")
    panels.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return panels[0]


@router.post("/panel/api/{panel_id}/confirm")
async def api_confirm_panel(panel_id: str):
    """Client confirms a panel — marks respondents as 'scheduled'."""
    path = PANELS_DIR / f"{panel_id}.json"
    if not path.exists():
        raise HTTPException(404, "Panel not found")
    panel = json.loads(path.read_text(encoding="utf-8"))
    # Find the project and create a PanelAgent to handle confirmation
    project = _load_project(panel.get("project_id", ""))
    agent = PanelAgent(project)
    ok = agent.confirm_panel(panel_id)
    if not ok:
        raise HTTPException(500, "Failed to confirm panel")
    return {"status": "confirmed", "panel_id": panel_id,
            "respondents_scheduled": len(panel.get("respondents", []))}
