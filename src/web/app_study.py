"""
app_study.py — Study lifecycle routes for the client portal.

Mounted in app.py. Routes:
  GET  /listen/study/new                        → new study page (brief chat)
  GET  /listen/study/{project_id}/pricing       → pricing page
  GET  /listen/study/{project_id}/timeline      → timeline + payment page
  GET  /listen/study/{project_id}/status        → live status page
  GET  /api/client/study/{project_id}/status    → status JSON (polled every 10s)
  GET  /api/client/study/{project_id}/report-link → share URL for completed report
  GET  /api/client/timeline/{project_id}        → timeline JSON
  POST /api/client/quote/compute                → compute quote with given params
  POST /api/client/payment/initiate             → initiate Razorpay or Stripe payment
  POST /api/client/payment/razorpay/verify      → verify Razorpay payment signature
  GET  /api/admin/pricing/link                  → redirect /admin to /admin/pricing
  GET  /admin/pricing                           → admin pricing config page
"""

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from config.settings import settings
from src.storage.pricing_store import compute_quote
from src.core.research_project import get_project

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
TEMPLATES = BASE_DIR / "src" / "web" / "templates"
PROJECTS_DIR = BASE_DIR / "projects"
PANELS_DIR = BASE_DIR / "panels"

PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
PANELS_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(tags=["study"])

# ── Pipeline stage order ──────────────────────────────────────────────────────

PIPELINE_STAGES = [
    "briefing",
    "pricing",
    "timeline_estimate",
    "payment",
    "panel_building",
    "panel_approval",
    "interviewing",
    "analysis",
    "report",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _html(name: str) -> HTMLResponse:
    f = TEMPLATES / name
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else f"<h1>{name} not found</h1>")


def _get_client_user(request: Request) -> Optional[Dict]:
    from src.storage.client_store import get_client
    client_id = request.session.get("client_id")
    if not client_id:
        return None
    return get_client(client_id)


def _require_client(request: Request) -> Dict:
    client = _get_client_user(request)
    if not client:
        raise HTTPException(303, headers={"Location": "/listen/login"})
    return client


def _is_admin(request: Request) -> bool:
    return request.session.get("is_admin") is True


def _require_admin(request: Request):
    if not _is_admin(request):
        raise HTTPException(303, headers={"Location": "/admin/login"})


def _load_project_json(project_id: str) -> Optional[Dict]:
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_project_json(project: Dict):
    path = PROJECTS_DIR / f"{project['project_id']}.json"
    path.write_text(json.dumps(project, indent=2, ensure_ascii=False))


def _update_pipeline(project: Dict, stage: str, status: str):
    """Update a single pipeline stage status + timestamp."""
    project.setdefault("pipeline", {})
    project["pipeline"].setdefault(stage, {})
    project["pipeline"][stage]["status"] = status
    now = datetime.now(timezone.utc).isoformat()
    if status == "completed":
        project["pipeline"][stage]["completed_at"] = now
    elif status == "active":
        project["pipeline"][stage]["started_at"] = now


def _mark_payment_received(project_id: str, payment_id: str, gateway: str):
    """Update project JSON to mark payment received and advance pipeline."""
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return
    project = json.loads(path.read_text(encoding="utf-8"))
    project["status"] = "panel_building"
    project["payment_received"] = True
    project["payment_id"] = payment_id
    project["payment_gateway"] = gateway
    project["payment_at"] = datetime.now(timezone.utc).isoformat()
    _update_pipeline(project, "payment", "completed")
    _update_pipeline(project, "panel_building", "active")
    path.write_text(json.dumps(project, indent=2, ensure_ascii=False))


async def _trigger_panel_building(project_id: str):
    """Background task: run PanelAgent after payment confirmed."""
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return
    project = json.loads(path.read_text(encoding="utf-8"))
    try:
        from src.agents.panel_agent import PanelAgent
        agent = PanelAgent(project)
        criteria = {"language": project.get("language", "en"), "not_interviewed_days": 30}
        panel = await agent.query_panel(criteria)
        if panel:
            # Re-read in case changed
            project = json.loads(path.read_text(encoding="utf-8"))
            project["status"] = "panel_approval"
            project["panel_id"] = panel.get("panel_id")
            _update_pipeline(project, "panel_building", "completed")
            _update_pipeline(project, "panel_approval", "active")
            path.write_text(json.dumps(project, indent=2, ensure_ascii=False))

            # Notify client
            try:
                from src.notifications.notifier import notify_client_milestone
                client_email = project.get("client_email", "")
                if client_email:
                    respondent_count = len(panel.get("respondents", []))
                    await notify_client_milestone(
                        client_email,
                        project.get("name", ""),
                        "Panel Ready for Approval",
                        f"We've recruited {respondent_count} respondents matching your criteria. "
                        "Please log in to review and approve the panel.",
                    )
            except Exception as notify_err:
                logger.warning(f"Notification failed for {project_id}: {notify_err}")
    except Exception as e:
        logger.error(f"Panel building failed for {project_id}: {e}", exc_info=True)


def _infer_pipeline(project: Dict) -> Dict:
    """
    Infer pipeline status from project fields when pipeline dict is absent or incomplete.
    Returns a full pipeline dict with 'pending' / 'completed' / 'active' stages.
    """
    pipeline = {}
    for stage in PIPELINE_STAGES:
        pipeline[stage] = {"status": "pending"}

    # Use existing pipeline data as the base if present
    existing = project.get("pipeline", {})
    for stage in PIPELINE_STAGES:
        if stage in existing:
            pipeline[stage] = dict(existing[stage])

    # Infer from project fields if not explicitly set
    questions_done = bool(project.get("questions"))
    payment_done = bool(project.get("payment_received"))
    panel_id = project.get("panel_id")
    report_id = project.get("report_id")
    status = project.get("status", "briefing")

    if pipeline["briefing"]["status"] == "pending" and questions_done:
        pipeline["briefing"]["status"] = "completed"

    if pipeline["pricing"]["status"] == "pending" and project.get("quote"):
        pipeline["pricing"]["status"] = "completed"

    if pipeline["timeline_estimate"]["status"] == "pending" and project.get("timeline"):
        pipeline["timeline_estimate"]["status"] = "completed"

    if pipeline["payment"]["status"] == "pending" and payment_done:
        pipeline["payment"]["status"] = "completed"

    if pipeline["panel_building"]["status"] == "pending" and (panel_id or status in ("panel_approval", "interviewing", "analysis", "report", "completed")):
        pipeline["panel_building"]["status"] = "completed"

    if pipeline["panel_approval"]["status"] == "pending" and status in ("interviewing", "analysis", "report", "completed"):
        pipeline["panel_approval"]["status"] = "completed"

    if pipeline["interviewing"]["status"] == "pending" and status in ("analysis", "report", "completed"):
        pipeline["interviewing"]["status"] = "completed"

    if pipeline["analysis"]["status"] == "pending" and status in ("report", "completed"):
        pipeline["analysis"]["status"] = "completed"

    if pipeline["report"]["status"] == "pending" and report_id:
        pipeline["report"]["status"] = "completed"

    # Mark the current active stage
    prev_done = True
    for stage in PIPELINE_STAGES:
        if pipeline[stage]["status"] == "pending" and prev_done:
            pipeline[stage]["status"] = "active"
            break
        prev_done = pipeline[stage]["status"] == "completed"

    return pipeline


def _find_panel_for_project(project_id: str) -> Optional[str]:
    """Search panels/ dir for a panel linked to this project_id. Returns panel_id or None."""
    for f in PANELS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("project_id") == project_id:
                return data.get("panel_id")
        except Exception:
            pass
    return None


def _find_report_for_project(project_id: str) -> Optional[str]:
    """Search reports/ dir for a report linked to this project_id. Returns report_id or None."""
    reports_dir = BASE_DIR / "reports"
    if not reports_dir.exists():
        return None
    for f in reports_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("project_id") == project_id:
                return data.get("report_id")
        except Exception:
            pass
    return None


# ── Page routes ───────────────────────────────────────────────────────────────

@router.get("/listen/study/new", response_class=HTMLResponse)
async def study_new_page(request: Request):
    if not _get_client_user(request):
        return RedirectResponse("/listen/login", status_code=303)
    return _html("study_new.html")


@router.get("/listen/study/{project_id}/pricing", response_class=HTMLResponse)
async def study_pricing_page(project_id: str, request: Request):
    if not _get_client_user(request):
        return RedirectResponse("/listen/login", status_code=303)
    project = _load_project_json(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return _html("study_pricing.html")


@router.get("/listen/study/{project_id}/timeline", response_class=HTMLResponse)
async def study_timeline_page(project_id: str, request: Request):
    if not _get_client_user(request):
        return RedirectResponse("/listen/login", status_code=303)
    project = _load_project_json(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return _html("study_timeline.html")


@router.get("/listen/study/{project_id}/status", response_class=HTMLResponse)
async def study_status_page(project_id: str, request: Request):
    if not _get_client_user(request):
        return RedirectResponse("/listen/login", status_code=303)
    project = _load_project_json(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return _html("study_status.html")


# ── Admin pricing page ────────────────────────────────────────────────────────

@router.get("/api/admin/pricing/link")
async def admin_pricing_redirect(request: Request):
    _require_admin(request)
    return RedirectResponse("/admin/pricing", status_code=303)


@router.get("/admin/pricing", response_class=HTMLResponse)
async def admin_pricing_page(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _html("admin_pricing.html")


# ── API: Study status (polled every 10s by client dashboard) ──────────────────

@router.get("/api/client/study/{project_id}/status")
async def api_study_status(project_id: str, request: Request):
    _require_client(request)

    project = _load_project_json(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    pipeline = _infer_pipeline(project)

    # Resolve panel_id — from project or scan panels/
    panel_id = project.get("panel_id") or _find_panel_for_project(project_id)

    # Resolve report_id — from project or scan reports/
    report_id = project.get("report_id") or _find_report_for_project(project_id)

    # Timeline-derived estimated report date
    estimated_report_date = None
    timeline = project.get("timeline") or {}
    if isinstance(timeline, dict):
        estimated_report_date = timeline.get("estimated_report_date")

    return {
        "project_id": project_id,
        "name": project.get("name", ""),
        "status": project.get("status", "briefing"),
        "research_type": project.get("research_type", "custom"),
        "pipeline": pipeline,
        "panel_id": panel_id,
        "report_id": report_id,
        "interviews_completed": project.get("interviews_completed", 0),
        "interviews_total": project.get("target_respondents", 10),
        "estimated_report_date": estimated_report_date,
    }


# ── API: Report share link ─────────────────────────────────────────────────────

@router.get("/api/client/study/{project_id}/report-link")
async def api_report_link(project_id: str, request: Request):
    _require_client(request)

    project = _load_project_json(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    report_id = project.get("report_id") or _find_report_for_project(project_id)
    if not report_id:
        raise HTTPException(404, "Report not yet available for this project")

    return {
        "report_id": report_id,
        "url": f"https://getheard.space/report/{report_id}",
    }


# ── API: Timeline ─────────────────────────────────────────────────────────────

@router.get("/api/client/timeline/{project_id}")
async def api_get_timeline(project_id: str, request: Request):
    _require_client(request)

    project = _load_project_json(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    existing_timeline = project.get("timeline")
    if existing_timeline:
        return existing_timeline

    # Timeline not yet computed — trigger async computation and return 202
    asyncio.create_task(_compute_and_save_timeline(project_id))
    return JSONResponse({"status": "computing"}, status_code=202)


async def _compute_and_save_timeline(project_id: str):
    """Background task: estimate timeline using TimelineAgent and save to project."""
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return
    project = json.loads(path.read_text(encoding="utf-8"))
    try:
        from src.agents.timeline_agent import TimelineAgent
        quote = project.get("quote", {})
        agent = TimelineAgent(project, quote)
        timeline = await agent.estimate()
        if timeline:
            project = json.loads(path.read_text(encoding="utf-8"))  # re-read
            project["timeline"] = timeline
            _update_pipeline(project, "timeline_estimate", "completed")
            path.write_text(json.dumps(project, indent=2, ensure_ascii=False))
            logger.info(f"Timeline computed for {project_id}: {timeline.get('total_min_days')}–{timeline.get('total_max_days')} days")
    except Exception as e:
        logger.error(f"Timeline estimation failed for {project_id}: {e}", exc_info=True)


# ── API: Compute quote (no auth — used for live preview) ─────────────────────

@router.post("/api/client/quote/compute")
async def api_compute_quote(request: Request):
    body = await request.json()

    required = ["study_type", "panel_size", "panel_source"]
    for field in required:
        if field not in body:
            raise HTTPException(400, f"Missing required field: {field}")

    try:
        panel_size = int(body["panel_size"])
    except (ValueError, TypeError):
        raise HTTPException(400, "panel_size must be an integer")

    try:
        quote = compute_quote(
            study_type=body["study_type"],
            panel_size=panel_size,
            panel_source=body["panel_source"],
            market=body.get("market", "IN"),
            industry=body.get("industry", "other"),
            urgency=bool(body.get("urgency", False)),
            respondent_incentive_per_head=int(body.get("respondent_incentive_per_head", 0)),
        )
        return quote
    except Exception as e:
        logger.error(f"Quote computation failed: {e}", exc_info=True)
        raise HTTPException(500, f"Quote computation failed: {e}")


# ── API: Initiate payment ─────────────────────────────────────────────────────

@router.post("/api/client/payment/initiate")
async def api_initiate_payment(request: Request):
    client = _require_client(request)
    client_id = client["client_id"]

    body = await request.json()
    project_id = body.get("project_id")
    method = body.get("method", "razorpay")

    if not project_id:
        raise HTTPException(400, "project_id is required")

    project = _load_project_json(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # Compute total from saved quote or recompute
    quote = project.get("quote") or {}
    total = quote.get("total", 0)
    if not total:
        raise HTTPException(400, "No quote found for this project. Please confirm pricing first.")

    total_paise = int(total * 100)  # INR → paise
    project_name = project.get("name", "GetHeard Study")

    if method == "razorpay":
        if not settings.has_razorpay:
            return {"error": "razorpay_not_configured"}
        try:
            import razorpay
            client_rp = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
            order = client_rp.order.create({
                "amount": total_paise,
                "currency": "INR",
                "receipt": f"getheard_{project_id}",
                "notes": {"project_id": project_id, "client_id": client_id},
            })
            return {
                "razorpay_order_id": order["id"],
                "key_id": settings.razorpay_key_id,
                "amount": total_paise,
                "currency": "INR",
                "project_id": project_id,
            }
        except ImportError:
            return {
                "error": "payment_gateway_not_installed",
                "message": "Contact hello@getheard.space",
            }
        except Exception as e:
            logger.error(f"Razorpay order creation failed for {project_id}: {e}", exc_info=True)
            raise HTTPException(500, f"Payment initiation failed: {e}")

    elif method == "stripe":
        if not settings.has_stripe:
            return {"error": "stripe_not_configured"}
        try:
            import stripe
            stripe.api_key = settings.stripe_secret_key
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "inr",
                        "product_data": {"name": project_name},
                        "unit_amount": total_paise,
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=f"https://getheard.space/listen/study/{project_id}/status?paid=1",
                cancel_url=f"https://getheard.space/listen/study/{project_id}/timeline",
                metadata={"project_id": project_id, "client_id": client_id},
            )
            return {"checkout_url": session.url}
        except ImportError:
            return {
                "error": "payment_gateway_not_installed",
                "message": "Contact hello@getheard.space",
            }
        except Exception as e:
            logger.error(f"Stripe session creation failed for {project_id}: {e}", exc_info=True)
            raise HTTPException(500, f"Payment initiation failed: {e}")

    else:
        raise HTTPException(400, f"Unsupported payment method: {method}. Use 'razorpay' or 'stripe'.")


# ── API: Verify Razorpay payment signature ────────────────────────────────────

@router.post("/api/client/payment/razorpay/verify")
async def api_verify_razorpay(request: Request):
    _require_client(request)
    body = await request.json()

    payment_id = body.get("razorpay_payment_id", "")
    order_id = body.get("razorpay_order_id", "")
    razorpay_signature = body.get("razorpay_signature", "")
    project_id = body.get("project_id", "")

    if not all([payment_id, order_id, razorpay_signature, project_id]):
        raise HTTPException(400, "Missing required fields: razorpay_payment_id, razorpay_order_id, razorpay_signature, project_id")

    if not settings.razorpay_key_secret:
        raise HTTPException(503, "Razorpay not configured on this server")

    # Verify HMAC-SHA256 signature
    generated = hmac.new(
        settings.razorpay_key_secret.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(generated, razorpay_signature):
        raise HTTPException(400, "Invalid payment signature")

    # Mark project as paid
    _mark_payment_received(project_id, payment_id, "razorpay")
    logger.info(f"Payment verified for project {project_id}: {payment_id}")

    # Trigger panel building in background
    asyncio.create_task(_trigger_panel_building(project_id))

    return {"status": "verified", "project_id": project_id}


# ── Helper: update_project_field (utility for other modules) ─────────────────

def update_project_field(project_id: str, field: str, value) -> bool:
    """Read the project JSON, update one field, and write it back. Returns True on success."""
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return False
    project = json.loads(path.read_text(encoding="utf-8"))
    project[field] = value
    project["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(project, indent=2, ensure_ascii=False))
    return True
