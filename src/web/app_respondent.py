"""
app_respondent.py — Respondent portal routes.

Routes:
  GET  /join/profile/{phone}              → respondent profile page
  GET  /join/rewards/{respondent_id}      → rewards/points dashboard
  POST /api/respondents/{id}/points/add   → add points (internal/admin use)
  POST /api/respondents/{id}/redeem       → submit redemption request
  GET  /api/respondents/{id}/points       → points balance + history
  GET  /api/respondents/{id}/redemptions  → redemption request history
  GET  /api/points/rates                  → exchange rates by country
  GET  /api/admin/redemptions             → all pending redemptions (admin)
  PATCH /api/admin/redemptions/{id}       → update redemption status (admin)
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.storage.points_store import (
    add_points,
    create_redemption_request,
    get_exchange_rates,
    get_points_balance,
    list_redemption_requests,
    update_redemption_status,
    EXCHANGE_RATES,
    MIN_REDEMPTION_POINTS,
)
from src.storage.respondent_store import get_respondent, list_respondents

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
TEMPLATES = BASE_DIR / "src" / "web" / "templates"

router = APIRouter(tags=["respondent"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _html(name: str) -> HTMLResponse:
    f = TEMPLATES / name
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else f"<h1>{name} not found</h1>")


def _is_admin(request: Request) -> bool:
    return request.session.get("is_admin") is True


# ── Request Models ────────────────────────────────────────────────────────────

class AddPointsRequest(BaseModel):
    amount: int
    reason: str
    study_id: Optional[str] = ""


class RedeemRequest(BaseModel):
    points: int
    method: str          # "upi" | "gift_card" | "bank_transfer"
    details: Dict        # {"upi_id": "..."} or {"card_brand": "amazon", "email": "..."}
    country: Optional[str] = "IN"


class RedemptionStatusUpdate(BaseModel):
    status: str          # "pending" | "processing" | "completed" | "failed"
    notes: Optional[str] = ""


# ── Page Routes ───────────────────────────────────────────────────────────────

@router.get("/join/profile/{phone}", response_class=HTMLResponse)
async def respondent_profile_page(phone: str):
    """Respondent profile page — looked up by phone number."""
    return _html("respondent_profile.html")


@router.get("/join/rewards/{respondent_id}", response_class=HTMLResponse)
async def respondent_rewards_page(respondent_id: str):
    """Respondent rewards/points dashboard."""
    return _html("respondent_rewards.html")


# ── Points API ────────────────────────────────────────────────────────────────

@router.get("/api/respondents/{respondent_id}/points")
async def api_get_points(respondent_id: str):
    """Return points balance and transaction history."""
    r = get_respondent(respondent_id)
    if not r:
        raise HTTPException(404, "Respondent not found")
    balance_data = get_points_balance(respondent_id)
    return {
        "respondent_id": respondent_id,
        "name": r.get("name"),
        "country": r.get("country", "IN"),
        **balance_data,
    }


@router.post("/api/respondents/{respondent_id}/points/add")
async def api_add_points(respondent_id: str, req: AddPointsRequest, request: Request):
    """Credit points to a respondent (internal / admin use only)."""
    if not _is_admin(request):
        raise HTTPException(403, "Admin access required")
    r = get_respondent(respondent_id)
    if not r:
        raise HTTPException(404, "Respondent not found")
    ok = add_points(respondent_id, req.amount, req.reason, req.study_id or "")
    if not ok:
        raise HTTPException(500, "Failed to add points")
    return {"status": "credited", "amount": req.amount, **get_points_balance(respondent_id)}


@router.post("/api/respondents/{respondent_id}/redeem")
async def api_redeem(respondent_id: str, req: RedeemRequest):
    """Submit a redemption request."""
    r = get_respondent(respondent_id)
    if not r:
        raise HTTPException(404, "Respondent not found")

    if req.points < MIN_REDEMPTION_POINTS:
        raise HTTPException(400, f"Minimum redemption is {MIN_REDEMPTION_POINTS} points")

    valid_methods = {"upi", "gift_card", "bank_transfer"}
    if req.method not in valid_methods:
        raise HTTPException(400, f"Invalid method. Must be one of: {valid_methods}")

    try:
        redemption = create_redemption_request(
            respondent_id=respondent_id,
            points=req.points,
            method=req.method,
            details=req.details,
            country=req.country or r.get("country", "IN"),
        )
        return {"status": "submitted", "redemption": redemption}
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        logger.error(f"Redemption error: {exc}", exc_info=True)
        raise HTTPException(500, str(exc))


@router.get("/api/respondents/{respondent_id}/redemptions")
async def api_get_redemptions(respondent_id: str):
    """Return redemption request history for a respondent."""
    r = get_respondent(respondent_id)
    if not r:
        raise HTTPException(404, "Respondent not found")
    redemptions = list_redemption_requests(respondent_id)
    return {"respondent_id": respondent_id, "redemptions": redemptions, "count": len(redemptions)}


# ── Exchange Rates API ────────────────────────────────────────────────────────

@router.get("/api/points/rates")
async def api_exchange_rates(country: str = "IN"):
    """Return exchange rate info and all country rates."""
    rates = get_exchange_rates(country)
    all_rates = {
        code: {
            **info,
            "gift_card_rate": round(info["rate"] * 1.10, 6),
        }
        for code, info in EXCHANGE_RATES.items()
    }
    return {
        "country": country,
        "rates": rates,
        "all_countries": all_rates,
        "min_redemption_points": MIN_REDEMPTION_POINTS,
    }


# ── Admin Redemptions API ─────────────────────────────────────────────────────

@router.get("/api/admin/redemptions")
async def api_admin_list_redemptions(request: Request, status: Optional[str] = None):
    """List all redemption requests (admin only)."""
    if not _is_admin(request):
        raise HTTPException(403, "Admin access required")
    all_redemptions = list_redemption_requests()
    if status:
        all_redemptions = [r for r in all_redemptions if r.get("status") == status]
    return {"redemptions": all_redemptions, "count": len(all_redemptions)}


@router.patch("/api/admin/redemptions/{redemption_id}")
async def api_admin_update_redemption(
    redemption_id: str,
    req: RedemptionStatusUpdate,
    request: Request,
):
    """Update status of a redemption request (admin only)."""
    if not _is_admin(request):
        raise HTTPException(403, "Admin access required")

    valid_statuses = {"pending", "processing", "completed", "failed"}
    if req.status not in valid_statuses:
        raise HTTPException(400, f"Invalid status. Must be one of: {valid_statuses}")

    updated = update_redemption_status(redemption_id, req.status, req.notes or "")
    if not updated:
        raise HTTPException(404, "Redemption request not found")
    return {"status": "updated", "redemption": updated}
