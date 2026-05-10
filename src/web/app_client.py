"""
app_client.py — Client portal routes.

Mounted in app.py. Handles:
  GET  /listen               → client dashboard (requires login)
  GET  /listen/login         → login page
  POST /listen/login         → authenticate
  GET  /listen/signup        → signup page
  POST /listen/api/signup    → create account
  GET  /listen/logout        → logout
  GET  /api/client/projects  → client's projects
  GET  /api/client/stats     → client stats
  POST /api/client/studies   → start a new study (triggers BriefAgent)
  GET  /api/client/quote/{project_id}  → get quote for a project
  POST /api/client/quote/{project_id}/confirm → confirm quote + trigger payment
  GET  /api/client/timeline/{project_id} → get timeline for a project
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from src.storage.client_store import create_client, authenticate_client, get_client, list_clients, add_study_to_client
from src.storage.pricing_store import compute_quote, load_pricing_config
from src.core.research_project import list_projects, get_project
from src.core.report_generator import list_reports

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
PROJECTS_DIR = BASE_DIR / "projects"
TEMPLATES = BASE_DIR / "src" / "web" / "templates"

router = APIRouter(tags=["client"])


def _html(name: str) -> HTMLResponse:
    f = TEMPLATES / name
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else f"<h1>{name} not found</h1>")


def _get_client_user(request: Request) -> Optional[Dict]:
    client_id = request.session.get("client_id")
    if not client_id:
        return None
    # Simple / demo credentials — stored in settings, not Firestore
    if client_id.startswith("simple:"):
        username = client_id[len("simple:"):]
        return {
            "client_id": client_id,
            "name": request.session.get("client_name", username.capitalize()),
            "company": request.session.get("client_company", "GetHeard Demo"),
            "email": username,
            "studies": [],
        }
    return get_client(client_id)


def _require_client(request: Request) -> Dict:
    client = _get_client_user(request)
    if not client:
        raise HTTPException(303, headers={"Location": "/listen/login"})
    return client


# ── Pages ─────────────────────────────────────────────────────────────────────

@router.get("/listen", response_class=HTMLResponse)
async def client_dashboard(request: Request):
    if not _get_client_user(request):
        return RedirectResponse("/listen/login", status_code=303)
    return _html("client_dashboard.html")


@router.get("/listen/signup", response_class=HTMLResponse)
async def client_signup_page():
    return _html("client_signup.html")


@router.get("/listen/login", response_class=HTMLResponse)
async def client_login_page(request: Request):
    if _get_client_user(request):
        return RedirectResponse("/listen", status_code=303)
    return _html("client_login.html")


@router.get("/listen/logout")
async def client_logout(request: Request):
    request.session.pop("client_id", None)
    request.session.pop("client_name", None)
    return RedirectResponse("/listen/login", status_code=303)


# ── Auth API ──────────────────────────────────────────────────────────────────

@router.post("/listen/api/signup")
async def client_signup_submit(request: Request, payload: dict = None):
    if payload is None:
        body = await request.json()
    else:
        body = payload
    try:
        client = create_client(body)
        request.session["client_id"] = client["client_id"]
        request.session["client_name"] = client["name"]
        return {"status": "created", "client_id": client["client_id"]}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Signup error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.post("/listen/login")
async def client_login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    from config.settings import settings

    # 1. Check simple credentials from settings (demo accounts, quick access)
    creds = settings.client_credentials_dict
    username = email.strip().lower()
    if username in creds and creds[username] == password:
        request.session["client_id"] = f"simple:{username}"
        request.session["client_name"] = username.capitalize()
        request.session["client_company"] = "GetHeard Demo"
        return RedirectResponse("/listen", status_code=303)

    # 2. Fall back to Firestore client accounts
    client = authenticate_client(email, password)
    if not client:
        return RedirectResponse("/listen/login?error=1", status_code=303)
    request.session["client_id"] = client["client_id"]
    request.session["client_name"] = client["name"]
    request.session["client_company"] = client.get("company", "")
    return RedirectResponse("/listen", status_code=303)


# ── Client API ────────────────────────────────────────────────────────────────

@router.get("/api/client/projects")
async def api_client_projects(request: Request):
    client = _require_client(request)
    study_ids = list(client.get("studies", []))
    # For simple/demo users, also include session-linked studies
    if client["client_id"].startswith("simple:"):
        for sid in request.session.get("linked_studies", []):
            if sid not in study_ids:
                study_ids.append(sid)
    projects = []
    for sid in study_ids:
        p = get_project(sid)
        if p:
            projects.append(p.to_dict())
    return {"projects": projects, "client": client["client_id"]}


@router.get("/api/client/stats")
async def api_client_stats(request: Request):
    client = _require_client(request)
    study_ids = list(client.get("studies", []))
    if client["client_id"].startswith("simple:"):
        for sid in request.session.get("linked_studies", []):
            if sid not in study_ids:
                study_ids.append(sid)
    active = completed = respondents = 0
    for sid in study_ids:
        p = get_project(sid)
        if p:
            d = p.to_dict()
            status = d.get("status", "active")
            if status == "completed":
                completed += 1
            else:
                active += 1
            respondents += d.get("interviews_completed", 0)
    return {
        "active_studies": active,
        "completed_studies": completed,
        "respondents_interviewed": respondents,
        "client": client["client_id"],
        "client_name": client.get("name", ""),
        "company": client.get("company", ""),
    }


@router.get("/listen/reports", response_class=HTMLResponse)
async def client_reports_page(request: Request):
    if not _get_client_user(request):
        return RedirectResponse("/listen/login", status_code=303)
    return _html("client_reports.html")


@router.get("/listen/studies", response_class=HTMLResponse)
async def client_studies_page(request: Request):
    if not _get_client_user(request):
        return RedirectResponse("/listen/login", status_code=303)
    return RedirectResponse("/listen", status_code=302)


@router.get("/listen/panel", response_class=HTMLResponse)
async def client_panel_page(request: Request):
    if not _get_client_user(request):
        return RedirectResponse("/listen/login", status_code=303)
    return RedirectResponse("/listen", status_code=302)


@router.get("/listen/billing", response_class=HTMLResponse)
async def client_billing_page(request: Request):
    if not _get_client_user(request):
        return RedirectResponse("/listen/login", status_code=303)
    return RedirectResponse("/listen", status_code=302)


@router.get("/listen/settings", response_class=HTMLResponse)
async def client_settings_page(request: Request):
    if not _get_client_user(request):
        return RedirectResponse("/listen/login", status_code=303)
    return RedirectResponse("/listen", status_code=302)


@router.get("/api/client/reports")
async def api_client_reports(request: Request):
    """Return reports for the logged-in client's projects."""
    client = _require_client(request)
    study_ids = set(client.get("studies", []))
    all_reports = list_reports()
    client_reports = [r for r in all_reports if r.get("project_id") in study_ids]
    return {"reports": client_reports, "client": client["client_id"]}


@router.post("/api/client/studies/{project_id}/link")
async def api_link_study(project_id: str, request: Request):
    """Link a project to the logged-in client's account after brief+design completes."""
    client = _require_client(request)
    client_id = client["client_id"]
    # For simple/demo users — store linked studies in session
    if client_id.startswith("simple:"):
        studies = request.session.get("linked_studies", [])
        if project_id not in studies:
            studies.append(project_id)
            request.session["linked_studies"] = studies
        return {"status": "linked", "project_id": project_id}
    # For Firestore users
    from src.storage.client_store import add_study_to_client
    ok = add_study_to_client(client_id, project_id)
    return {"status": "linked" if ok else "not_found", "project_id": project_id}


@router.get("/api/client/quote/{project_id}")
async def api_get_quote(project_id: str, request: Request):
    _require_client(request)
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    d = proj.to_dict()
    quote = compute_quote(
        study_type=d.get("research_type", "custom"),
        panel_size=d.get("target_respondents", 10),
        panel_source=d.get("panel_source", "csv"),
        market=d.get("market", "IN"),
        industry=d.get("industry", "other"),
    )
    return quote


@router.post("/api/client/quote/{project_id}/confirm")
async def api_confirm_quote(project_id: str, request: Request):
    """
    Confirm quote params → save to project JSON, mark briefing+pricing as complete,
    redirect client to the timeline page.
    """
    client = _require_client(request)
    body = await request.json()

    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        raise HTTPException(404, "Project not found")

    project = json.loads(path.read_text(encoding="utf-8"))

    # Save quote params and computed quote to project JSON
    quote_params = {
        "study_type":                    body.get("study_type", project.get("research_type", "custom")),
        "panel_size":                    int(body.get("panel_size", project.get("target_respondents", 10))),
        "panel_source":                  body.get("panel_source", "csv"),
        "market":                        body.get("market", project.get("market", "IN")),
        "industry":                      body.get("industry", project.get("industry", "other")),
        "urgency":                       bool(body.get("urgency", False)),
        "respondent_incentive_per_head": int(body.get("respondent_incentive_per_head", 0)),
    }

    # Compute the actual quote breakdown
    try:
        quote = compute_quote(**quote_params)
    except Exception as e:
        logger.error(f"Quote computation failed during confirm for {project_id}: {e}")
        raise HTTPException(500, f"Quote computation failed: {e}")

    project["quote_params"] = quote_params
    project["quote"] = quote
    project["target_respondents"] = quote_params["panel_size"]
    project["market"] = quote_params["market"]
    project["panel_source"] = quote_params["panel_source"]
    project["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Advance pipeline: mark briefing + pricing as completed
    now = datetime.now(timezone.utc).isoformat()
    pipeline = project.setdefault("pipeline", {})
    for stage in ("briefing", "pricing"):
        pipeline.setdefault(stage, {})
        pipeline[stage]["status"] = "completed"
        if "completed_at" not in pipeline[stage]:
            pipeline[stage]["completed_at"] = now

    # Advance status to pricing (if still at briefing)
    if project.get("status") in (None, "briefing", "active"):
        project["status"] = "pricing"

    path.write_text(json.dumps(project, indent=2, ensure_ascii=False))
    logger.info(f"Quote confirmed for project {project_id}: total={quote.get('total')}")

    return {
        "status": "confirmed",
        "project_id": project_id,
        "quote": quote,
        "redirect": f"/listen/study/{project_id}/timeline",
    }
