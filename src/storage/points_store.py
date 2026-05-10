"""
points_store.py — Firestore persistence for points and redemptions.
Collections: respondents/{id} (points fields), redemptions/{id}
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from google.cloud.firestore_v1 import ArrayUnion
from src.storage.firestore_db import db, RESPONDENTS, REDEMPTIONS

logger = logging.getLogger(__name__)

EXCHANGE_RATES = {
    "IN":    {"currency": "INR", "symbol": "₹",  "rate": 0.50,   "label": "₹0.50 per point"},
    "SG":    {"currency": "SGD", "symbol": "S$",  "rate": 0.01,   "label": "S$0.01 per point"},
    "ID":    {"currency": "IDR", "symbol": "Rp",  "rate": 75.0,   "label": "Rp75 per point"},
    "TH":    {"currency": "THB", "symbol": "฿",   "rate": 0.20,   "label": "฿0.20 per point"},
    "VN":    {"currency": "VND", "symbol": "₫",   "rate": 120.0,  "label": "₫120 per point"},
    "PH":    {"currency": "PHP", "symbol": "₱",   "rate": 0.28,   "label": "₱0.28 per point"},
    "MY":    {"currency": "MYR", "symbol": "RM",  "rate": 0.022,  "label": "RM0.022 per point"},
    "JP":    {"currency": "JPY", "symbol": "¥",   "rate": 0.75,   "label": "¥0.75 per point"},
    "KR":    {"currency": "KRW", "symbol": "₩",   "rate": 6.5,    "label": "₩6.5 per point"},
    "CN":    {"currency": "CNY", "symbol": "¥",   "rate": 0.036,  "label": "¥0.036 per point"},
    "OTHER": {"currency": "USD", "symbol": "$",   "rate": 0.006,  "label": "$0.006 per point"},
}

GIFT_CARD_BONUS_PERCENT = 10
CASH_UPI_COUNTRIES = {"IN", "SG"}
MIN_REDEMPTION_POINTS = 100


def get_points_balance(respondent_id: str) -> Dict:
    doc = db.collection(RESPONDENTS).document(respondent_id).get()
    if not doc.exists:
        return {"balance": 0, "lifetime_earned": 0, "transactions": []}
    r = doc.to_dict()
    return {
        "balance":        r.get("points_balance", 0),
        "lifetime_earned": r.get("points_lifetime", 0),
        "transactions":   r.get("points_transactions", []),
    }


def add_points(respondent_id: str, amount: int, reason: str, study_id: str = "") -> bool:
    doc_ref = db.collection(RESPONDENTS).document(respondent_id)
    doc = doc_ref.get()
    if not doc.exists:
        return False
    r = doc.to_dict()
    new_balance = r.get("points_balance", 0) + amount
    new_lifetime = r.get("points_lifetime", 0) + amount
    txn = {
        "type": "credit", "amount": amount, "reason": reason,
        "study_id": study_id, "balance_after": new_balance,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    doc_ref.update({
        "points_balance":  new_balance,
        "points_lifetime": new_lifetime,
        "points_transactions": ArrayUnion([txn]),
    })
    logger.info(f"Points credited: {respondent_id} +{amount}")
    return True


def deduct_points(respondent_id: str, amount: int, reason: str) -> bool:
    doc_ref = db.collection(RESPONDENTS).document(respondent_id)
    doc = doc_ref.get()
    if not doc.exists:
        return False
    r = doc.to_dict()
    current = r.get("points_balance", 0)
    if current < amount:
        return False
    new_balance = current - amount
    txn = {
        "type": "debit", "amount": amount, "reason": reason,
        "balance_after": new_balance,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    doc_ref.update({
        "points_balance": new_balance,
        "points_transactions": ArrayUnion([txn]),
    })
    return True


def create_redemption_request(
    respondent_id: str, points: int, method: str,
    details: Dict, country: str = "IN"
) -> Optional[Dict]:
    if points < MIN_REDEMPTION_POINTS:
        raise ValueError(f"Minimum redemption is {MIN_REDEMPTION_POINTS} points")

    rate_info = EXCHANGE_RATES.get(country, EXCHANGE_RATES["OTHER"])
    effective_rate = rate_info["rate"] * (1 + GIFT_CARD_BONUS_PERCENT / 100) \
        if method == "gift_card" else rate_info["rate"]
    value = round(points * effective_rate, 2)

    if not deduct_points(respondent_id, points, f"Redemption: {method} {value} {rate_info['currency']}"):
        raise ValueError("Insufficient points balance")

    req_id = str(uuid.uuid4())[:8]
    request = {
        "redemption_id":  req_id,
        "respondent_id":  respondent_id,
        "points":         points,
        "method":         method,
        "value":          value,
        "currency":       rate_info["currency"],
        "details":        details,
        "status":         "pending",
        "country":        country,
        "created_at":     datetime.now(timezone.utc).isoformat(),
        "processed_at":   None,
        "notes":          "",
    }
    db.collection(REDEMPTIONS).document(req_id).set(request)
    logger.info(f"Redemption {req_id}: {respondent_id} {points}pts → {value} {rate_info['currency']}")
    return request


def list_redemption_requests(respondent_id: str = None, status: str = None) -> List[Dict]:
    query = db.collection(REDEMPTIONS)
    if respondent_id:
        query = query.where("respondent_id", "==", respondent_id)
    if status:
        query = query.where("status", "==", status)
    docs = query.order_by("created_at", direction="DESCENDING").stream()
    return [d.to_dict() for d in docs]


def update_redemption_status(redemption_id: str, status: str, notes: str = "") -> Optional[Dict]:
    doc_ref = db.collection(REDEMPTIONS).document(redemption_id)
    doc = doc_ref.get()
    if not doc.exists:
        return None
    updates = {"status": status}
    if notes:
        updates["notes"] = notes
    if status in ("completed", "failed"):
        updates["processed_at"] = datetime.now(timezone.utc).isoformat()
    doc_ref.update(updates)
    logger.info(f"Redemption {redemption_id} → {status}")
    return {**doc.to_dict(), **updates}


def get_exchange_rates(country: str = "IN") -> Dict:
    rates = EXCHANGE_RATES.get(country, EXCHANGE_RATES["OTHER"])
    return {
        **rates,
        "gift_card_rate":         rates["rate"] * (1 + GIFT_CARD_BONUS_PERCENT / 100),
        "gift_card_bonus_percent": GIFT_CARD_BONUS_PERCENT,
        "min_redemption_points":   MIN_REDEMPTION_POINTS,
        "upi_available":           country in CASH_UPI_COUNTRIES,
        "cash_available":          country in CASH_UPI_COUNTRIES,
    }
