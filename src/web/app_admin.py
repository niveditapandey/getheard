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
import logging
from pathlib import Path
from typing import Optional, Dict

from fastapi import APIRouter, Form, HTTPException, Request
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
