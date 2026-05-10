"""
app_admin.py — Admin portal routes (owner only).

Routes:
  GET  /admin              → admin dashboard
  GET  /admin/login        → login page
  POST /admin/login        → authenticate
  GET  /admin/logout       → logout
  GET  /admin/pricing      → pricing config page
  GET  /api/admin/stats    → all platform stats
  GET  /api/admin/clients  → all clients
  GET  /api/admin/studies  → all studies
  GET  /api/admin/pricing  → current pricing config
  POST /api/admin/pricing  → update pricing config
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List

from fastapi import APIRouter, Body, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from config.settings import settings
from src.storage.client_store import list_clients
from src.storage.pricing_store import load_pricing_config, save_pricing_config
from src.storage.respondent_store import get_stats as panel_stats
from src.core.research_project import list_projects
from src.core.report_generator import list_reports

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
TEMPLATES = BASE_DIR / "src" / "web" / "templates"

router = APIRouter(tags=["admin"])


def _html(name: str) -> HTMLResponse:
    f = TEMPLATES / name
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else f"<h1>{name} not found</h1>")


def _is_admin(request: Request) -> bool:
    return request.session.get("is_admin") is True


def _require_admin(request: Request):
    if not _is_admin(request):
        raise HTTPException(303, headers={"Location": "/admin/login"})


# ── Pages ──────────────────────────────────────────────────────────────────────

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _html("admin_dashboard.html")


@router.get("/admin/clients", response_class=HTMLResponse)
async def admin_clients_page(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _html("admin_clients.html")


@router.get("/admin/clients/{client_id}", response_class=HTMLResponse)
async def admin_client_detail(client_id: str, request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _html("admin_clients.html")


@router.get("/admin/studies", response_class=HTMLResponse)
async def admin_studies_page(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _html("admin_studies.html")


@router.get("/admin/studies/{study_id}", response_class=HTMLResponse)
async def admin_study_detail(study_id: str, request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _html("admin_studies.html")


@router.get("/admin/respondents", response_class=HTMLResponse)
async def admin_respondents_page(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _html("admin_respondents.html")


@router.get("/admin/reports", response_class=HTMLResponse)
async def admin_reports_page(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _html("admin_reports.html")


@router.get("/admin/payouts", response_class=HTMLResponse)
async def admin_payouts_page(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _html("admin_payouts.html")


@router.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings_page(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _html("admin_settings.html")


@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    if _is_admin(request):
        return RedirectResponse("/admin", status_code=303)
    return _html("admin_login.html")


@router.get("/admin/logout")
async def admin_logout(request: Request):
    request.session.pop("is_admin", None)
    return RedirectResponse("/admin/login", status_code=303)


# ── Auth ───────────────────────────────────────────────────────────────────────

@router.post("/admin/login")
async def admin_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    creds = settings.client_credentials_dict  # reuse admin creds from settings
    # Admin login uses a special key "admin" in credentials
    admin_creds = settings.admin_credentials_dict
    if admin_creds.get(username) == password:
        request.session["is_admin"] = True
        request.session["admin_user"] = username
        return RedirectResponse("/admin", status_code=303)
    return RedirectResponse("/admin/login?error=1", status_code=303)


# ── Admin API ──────────────────────────────────────────────────────────────────

@router.get("/api/admin/stats")
async def api_admin_stats(request: Request):
    _require_admin(request)
    clients = list_clients()
    projects = list_projects()
    reports = list_reports()
    p_stats = panel_stats()

    completed = [p for p in projects if p.get("status") == "completed"]

    return {
        "total_clients": len(clients),
        "active_studies": len([p for p in projects if p.get("status") not in ("completed","cancelled")]),
        "total_respondents": p_stats.get("total", 0),
        "completed_this_month": len(completed),
        "revenue_this_month_inr": 0,  # TODO: connect to payment records
        "panel_stats": p_stats,
        "total_reports": len(reports),
    }


@router.get("/api/admin/clients")
async def api_admin_clients(request: Request):
    _require_admin(request)
    return {"clients": list_clients()}


@router.get("/api/admin/studies")
async def api_admin_studies(request: Request):
    _require_admin(request)
    return {"studies": list_projects()}


@router.get("/api/admin/pricing")
async def api_admin_pricing(request: Request):
    _require_admin(request)
    return load_pricing_config()


@router.post("/api/admin/pricing")
async def api_update_pricing(request: Request):
    _require_admin(request)
    body = await request.json()
    try:
        save_pricing_config(body)
        return {"status": "updated"}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Pipeline ────────────────────────────────────────────────────────────────────

PROJECTS_DIR = BASE_DIR / "projects"

def _classify_stage(p: Dict) -> str:
    """Map project fields → one of 5 CRM stages."""
    status = p.get("status", "briefing")
    if status == "won":
        return "won"
    if status == "payment_intent" or p.get("payment_intent"):
        return "proposals_accepted"
    pipeline = p.get("pipeline", {})
    pricing_done  = pipeline.get("pricing",  {}).get("status") == "completed"
    briefing_done = pipeline.get("briefing", {}).get("status") == "completed"
    if pricing_done:
        return "proposals_sent"
    if briefing_done:
        return "briefs"
    return "leads"

def _deal_value(p: Dict) -> int:
    q = p.get("quote", {})
    if isinstance(q, dict) and q.get("total"):
        return int(q["total"])
    return int(p.get("target_respondents", 10)) * 1000  # rough ₹1k/respondent estimate

def _project_summary(p: Dict) -> Dict:
    return {
        "project_id":    p.get("project_id", ""),
        "name":          p.get("name", "Untitled"),
        "research_type": p.get("research_type", ""),
        "client_id":     p.get("client_id", ""),
        "created_at":    p.get("created_at", ""),
        "updated_at":    p.get("updated_at", ""),
        "deal_value":    _deal_value(p),
        "stage":         _classify_stage(p),
        "status":        p.get("status", ""),
        "language":      p.get("language", "en"),
        "respondents":   p.get("target_respondents", 0),
    }

@router.get("/admin/pipeline", response_class=HTMLResponse)
async def admin_pipeline_page(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _html("admin_pipeline.html")

@router.get("/api/admin/pipeline")
async def api_admin_pipeline(request: Request):
    _require_admin(request)

    STAGE_ORDER = ["leads", "briefs", "proposals_sent", "proposals_accepted", "won"]
    stages: Dict[str, Dict] = {s: {"count": 0, "total_value": 0, "records": []} for s in STAGE_ORDER}

    for path in sorted(PROJECTS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            p = json.loads(path.read_text(encoding="utf-8"))
            stage = _classify_stage(p)
            val   = _deal_value(p)
            stages[stage]["count"]       += 1
            stages[stage]["total_value"] += val
            stages[stage]["records"].append(_project_summary(p))
        except Exception:
            pass

    # Funnel conversion rates (sequential)
    funnel = []
    base = stages["leads"]["count"] or 1
    for i, stage in enumerate(STAGE_ORDER):
        count = stages[stage]["count"]
        prev_count = stages[STAGE_ORDER[i-1]]["count"] if i > 0 else count
        funnel.append({
            "stage":       stage,
            "count":       count,
            "pct_of_top":  round(count / base * 100),
            "conv_from_prev": round(count / (prev_count or 1) * 100) if i > 0 else 100,
            "drop_from_prev": round((1 - count / (prev_count or 1)) * 100) if i > 0 else 0,
        })

    return {
        "stages":     stages,
        "funnel":     funnel,
        "total_pipeline_value": sum(stages[s]["total_value"] for s in STAGE_ORDER),
        "total_deals": sum(stages[s]["count"] for s in STAGE_ORDER),
    }

@router.patch("/api/admin/projects/{project_id}/stage")
async def api_move_stage(project_id: str, request: Request, body: Dict = Body(...)):
    _require_admin(request)
    new_stage = body.get("stage")
    VALID = {"leads", "briefs", "proposals_sent", "proposals_accepted", "won"}
    if new_stage not in VALID:
        raise HTTPException(400, f"stage must be one of {VALID}")

    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        raise HTTPException(404, "Project not found")

    p = json.loads(path.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat()

    # Apply stage → status/pipeline mapping
    pipeline = p.setdefault("pipeline", {})
    if new_stage == "briefs":
        pipeline.setdefault("briefing", {})["status"] = "completed"
        pipeline.setdefault("briefing", {}).setdefault("completed_at", now)
        p["status"] = "briefing"
    elif new_stage == "proposals_sent":
        pipeline.setdefault("briefing", {})["status"] = "completed"
        pipeline.setdefault("pricing",  {})["status"] = "completed"
        pipeline.setdefault("pricing",  {}).setdefault("completed_at", now)
        p["status"] = "pricing"
    elif new_stage == "proposals_accepted":
        p["status"] = "payment_intent"
        p["payment_intent"] = True
        p["payment_intent_at"] = now
    elif new_stage == "won":
        p["status"] = "won"
        p["won_at"]  = now
        pipeline.setdefault("delivery", {})["status"] = "pending"
    elif new_stage == "leads":
        p["status"] = "briefing"

    p["updated_at"] = now
    path.write_text(json.dumps(p, indent=2, ensure_ascii=False))
    return {"status": "moved", "project_id": project_id, "new_stage": new_stage}
