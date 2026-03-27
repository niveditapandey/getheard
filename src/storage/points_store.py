"""
points_store.py — Points and rewards tracking for GetHeard respondents.

Points lifecycle:
  - Credited 20% on study selection, 80% on completion
  - Redeemable for: gift cards, UPI cash (India/Singapore), coming soon elsewhere
  - Exchange rate: 100 points = ₹50 / S$1 / Rp 7,500 / ฿20 / ₫12,000

Redemption requests stored in redemptions/{respondent_id}_{timestamp}.json
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
RESPONDENTS_DIR = BASE_DIR / "respondents"
REDEMPTIONS_DIR = BASE_DIR / "redemptions"
REDEMPTIONS_DIR.mkdir(exist_ok=True)

# Exchange rates: points → local currency
EXCHANGE_RATES = {
    "IN":  {"currency": "INR", "symbol": "₹",  "rate": 0.50,   "label": "₹0.50 per point"},
    "SG":  {"currency": "SGD", "symbol": "S$",  "rate": 0.01,   "label": "S$0.01 per point"},
    "ID":  {"currency": "IDR", "symbol": "Rp",  "rate": 75.0,   "label": "Rp75 per point"},
    "TH":  {"currency": "THB", "symbol": "฿",   "rate": 0.20,   "label": "฿0.20 per point"},
    "VN":  {"currency": "VND", "symbol": "₫",   "rate": 120.0,  "label": "₫120 per point"},
    "PH":  {"currency": "PHP", "symbol": "₱",   "rate": 0.28,   "label": "₱0.28 per point"},
    "MY":  {"currency": "MYR", "symbol": "RM",  "rate": 0.022,  "label": "RM0.022 per point"},
    "JP":  {"currency": "JPY", "symbol": "¥",   "rate": 0.75,   "label": "¥0.75 per point"},
    "KR":  {"currency": "KRW", "symbol": "₩",   "rate": 6.5,    "label": "₩6.5 per point"},
    "CN":  {"currency": "CNY", "symbol": "¥",   "rate": 0.036,  "label": "¥0.036 per point"},
    "AU":  {"currency": "AUD", "symbol": "A$",  "rate": 0.0075, "label": "A$0.0075 per point"},
    "OTHER": {"currency": "USD", "symbol": "$",  "rate": 0.006,  "label": "$0.006 per point"},
}

GIFT_CARD_BONUS_PERCENT = 10  # Gift cards get 10% better value than cash
CASH_UPI_COUNTRIES = {"IN", "SG"}  # Countries where UPI payout is live
MIN_REDEMPTION_POINTS = 100


def _respondent_path(respondent_id: str) -> Path:
    return RESPONDENTS_DIR / f"{respondent_id}.json"


def get_points_balance(respondent_id: str) -> Dict:
    """Return points balance and transaction history for a respondent."""
    path = _respondent_path(respondent_id)
    if not path.exists():
        return {"balance": 0, "lifetime_earned": 0, "transactions": []}
    r = json.loads(path.read_text(encoding="utf-8"))
    return {
        "balance": r.get("points_balance", 0),
        "lifetime_earned": r.get("points_lifetime", 0),
        "transactions": r.get("points_transactions", []),
    }


def add_points(respondent_id: str, amount: int, reason: str, study_id: str = "") -> bool:
    """Credit points to a respondent."""
    path = _respondent_path(respondent_id)
    if not path.exists():
        return False
    r = json.loads(path.read_text(encoding="utf-8"))
    r["points_balance"] = r.get("points_balance", 0) + amount
    r["points_lifetime"] = r.get("points_lifetime", 0) + amount
    r.setdefault("points_transactions", []).append({
        "type": "credit",
        "amount": amount,
        "reason": reason,
        "study_id": study_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "balance_after": r["points_balance"],
    })
    path.write_text(json.dumps(r, indent=2, ensure_ascii=False))
    logger.info(f"Points credited: {respondent_id} +{amount} ({reason})")
    return True


def deduct_points(respondent_id: str, amount: int, reason: str) -> bool:
    """Deduct points (for redemption). Returns False if insufficient balance."""
    path = _respondent_path(respondent_id)
    if not path.exists():
        return False
    r = json.loads(path.read_text(encoding="utf-8"))
    current = r.get("points_balance", 0)
    if current < amount:
        return False
    r["points_balance"] = current - amount
    r.setdefault("points_transactions", []).append({
        "type": "debit",
        "amount": amount,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "balance_after": r["points_balance"],
    })
    path.write_text(json.dumps(r, indent=2, ensure_ascii=False))
    return True


def create_redemption_request(
    respondent_id: str,
    points: int,
    method: str,          # "upi" | "gift_card" | "bank_transfer"
    details: Dict,        # {"upi_id": "..."} or {"card_brand": "amazon", "email": "..."}
    country: str = "IN",
) -> Optional[Dict]:
    """Create a redemption request. Deducts points immediately."""
    if points < MIN_REDEMPTION_POINTS:
        raise ValueError(f"Minimum redemption is {MIN_REDEMPTION_POINTS} points")

    rate_info = EXCHANGE_RATES.get(country, EXCHANGE_RATES["OTHER"])

    # Gift cards get bonus rate
    if method == "gift_card":
        effective_rate = rate_info["rate"] * (1 + GIFT_CARD_BONUS_PERCENT / 100)
    else:
        effective_rate = rate_info["rate"]

    value = round(points * effective_rate, 2)

    if not deduct_points(respondent_id, points, f"Redemption: {method} {value} {rate_info['currency']}"):
        raise ValueError("Insufficient points balance")

    req_id = str(uuid.uuid4())[:8]
    request = {
        "redemption_id": req_id,
        "respondent_id": respondent_id,
        "points": points,
        "method": method,
        "value": value,
        "currency": rate_info["currency"],
        "details": details,
        "status": "pending",   # pending → processing → completed | failed
        "country": country,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "processed_at": None,
        "notes": "",
    }

    path = REDEMPTIONS_DIR / f"{respondent_id}_{req_id}.json"
    path.write_text(json.dumps(request, indent=2, ensure_ascii=False))
    logger.info(f"Redemption request: {req_id} — {respondent_id} {points}pts → {value} {rate_info['currency']} via {method}")
    return request


def list_redemption_requests(respondent_id: str = None) -> List[Dict]:
    """List redemption requests. Pass respondent_id to filter, or None for all (admin)."""
    requests = []
    for p in REDEMPTIONS_DIR.glob("*.json"):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
            if respondent_id is None or r.get("respondent_id") == respondent_id:
                requests.append(r)
        except Exception:
            pass
    requests.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return requests


def update_redemption_status(redemption_id: str, status: str, notes: str = "") -> Optional[Dict]:
    """Update status of a redemption request by ID. Returns updated record or None."""
    for p in REDEMPTIONS_DIR.glob("*.json"):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
            if r.get("redemption_id") == redemption_id:
                r["status"] = status
                if notes:
                    r["notes"] = notes
                if status in ("completed", "failed"):
                    r["processed_at"] = datetime.now(timezone.utc).isoformat()
                p.write_text(json.dumps(r, indent=2, ensure_ascii=False))
                logger.info(f"Redemption {redemption_id} status → {status}")
                return r
        except Exception:
            pass
    return None


def get_exchange_rates(country: str = "IN") -> Dict:
    """Return exchange rate info for a country."""
    rates = EXCHANGE_RATES.get(country, EXCHANGE_RATES["OTHER"])
    gift_rate = rates["rate"] * (1 + GIFT_CARD_BONUS_PERCENT / 100)
    return {
        **rates,
        "gift_card_rate": gift_rate,
        "gift_card_bonus_percent": GIFT_CARD_BONUS_PERCENT,
        "min_redemption_points": MIN_REDEMPTION_POINTS,
        "upi_available": country in CASH_UPI_COUNTRIES,
        "cash_available": country in CASH_UPI_COUNTRIES,
    }
