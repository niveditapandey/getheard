"""
respondent_store.py — Firestore persistence for the GetHeard respondent panel.
Collection: respondents/{respondent_id}
Sensitive fields stored in a sub-map, never returned in list queries.
"""
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.storage.firestore_db import db, RESPONDENTS

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {"name", "phone", "language", "consent_contact"}

AGE_RANGES = ["18-24", "25-34", "35-44", "45-54", "55+"]
GENDERS    = ["male", "female", "non_binary", "prefer_not_to_say", "other"]
LANGUAGES  = ["en", "hi", "id", "fil", "th", "vi", "ko", "ja", "zh"]
INTERESTS  = ["fintech", "ecommerce", "food", "travel", "healthcare",
              "education", "tech", "real_estate", "insurance", "gaming"]


def _clean_phone(raw: str) -> str:
    digits = re.sub(r"[^\d+]", "", raw.strip())
    if digits and not digits.startswith("+"):
        digits = "+" + digits
    return digits


def _safe_view(r: Dict) -> Dict:
    v = dict(r)
    v.pop("sensitive", None)
    return v


def _find_by_phone(phone: str) -> Optional[Dict]:
    docs = db.collection(RESPONDENTS).where("phone", "==", phone).limit(1).stream()
    for doc in docs:
        return doc.to_dict()
    return None


def enroll_respondent(data: Dict[str, Any]) -> Dict:
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    if not data.get("consent_contact"):
        raise ValueError("Respondent must consent to be contacted.")

    phone = _clean_phone(str(data.get("phone", "")))
    if len(phone) < 7:
        raise ValueError("Invalid phone number.")

    existing = _find_by_phone(phone)
    if existing:
        logger.info(f"Re-enrollment for phone {phone[:6]}*** → updating")
        return _update_respondent(existing["respondent_id"], data)

    respondent_id = str(uuid.uuid4())[:8]
    respondent = {
        "respondent_id":        respondent_id,
        "name":                 str(data["name"]).strip(),
        "phone":                phone,
        "whatsapp_number":      _clean_phone(str(data.get("whatsapp_number", phone))),
        "email":                str(data.get("email", "")).strip().lower() or None,
        "language":             data.get("language", "en"),
        "city":                 str(data.get("city", "")).strip() or None,
        "country":              str(data.get("country", "")).strip() or None,
        "age_range":            data.get("age_range"),
        "gender":               data.get("gender"),
        "interests":            data.get("interests", []),
        "consent_contact":      bool(data.get("consent_contact", False)),
        "enrolled_at":          datetime.now(timezone.utc).isoformat(),
        "last_updated":         datetime.now(timezone.utc).isoformat(),
        "source":               data.get("source", "web_form"),
        "status":               "active",
        "interviews_completed": 0,
        "last_interviewed_at":  None,
        "sensitive": {
            "sexual_orientation": data.get("sexual_orientation"),
            "medical_conditions": str(data.get("medical_conditions", "")).strip() or None,
        },
    }
    db.collection(RESPONDENTS).document(respondent_id).set(respondent)
    logger.info(f"Respondent enrolled: {respondent_id} ({respondent['language']})")
    return _safe_view(respondent)


def get_respondent(respondent_id: str) -> Optional[Dict]:
    doc = db.collection(RESPONDENTS).document(respondent_id).get()
    if not doc.exists:
        return None
    return _safe_view(doc.to_dict())


def get_respondent_full(respondent_id: str) -> Optional[Dict]:
    doc = db.collection(RESPONDENTS).document(respondent_id).get()
    return doc.to_dict() if doc.exists else None


def update_respondent_status(respondent_id: str, status: str) -> bool:
    doc_ref = db.collection(RESPONDENTS).document(respondent_id)
    doc = doc_ref.get()
    if not doc.exists:
        return False
    updates = {
        "status": status,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
    if status == "interviewed":
        r = doc.to_dict()
        updates["interviews_completed"] = r.get("interviews_completed", 0) + 1
        updates["last_interviewed_at"] = datetime.now(timezone.utc).isoformat()
    doc_ref.update(updates)
    return True


def list_respondents(filters: Optional[Dict] = None) -> List[Dict]:
    query = db.collection(RESPONDENTS)
    # Apply simple equality filters directly in Firestore
    if filters:
        for k in ("language", "status", "city", "age_range", "gender", "country"):
            if k in filters and filters[k]:
                query = query.where(k, "==", filters[k])
    docs = query.stream()
    results = []
    for doc in docs:
        r = doc.to_dict()
        # Client-side filter for interests (list intersection)
        if filters and "interests" in filters:
            if not set(filters["interests"]).intersection(set(r.get("interests", []))):
                continue
        results.append(_safe_view(r))
    return results


def search_respondents(criteria: Dict) -> List[Dict]:
    exclude = set(criteria.get("exclude_ids", []))
    query = db.collection(RESPONDENTS).where("status", "in", ["active", "enrolled"])
    if criteria.get("language"):
        query = query.where("language", "==", criteria["language"])
    docs = query.stream()
    scored = []
    for doc in docs:
        r = doc.to_dict()
        if r["respondent_id"] in exclude:
            continue
        score = _score(r, criteria)
        if score > 0:
            scored.append((_safe_view(r), score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [r for r, _ in scored]


def get_stats() -> Dict:
    langs: Dict[str, int] = {}
    ages: Dict[str, int] = {}
    genders: Dict[str, int] = {}
    statuses: Dict[str, int] = {}
    total = 0
    for doc in db.collection(RESPONDENTS).stream():
        r = doc.to_dict()
        total += 1
        langs[r.get("language", "?")] = langs.get(r.get("language", "?"), 0) + 1
        if r.get("age_range"):
            ages[r["age_range"]] = ages.get(r["age_range"], 0) + 1
        if r.get("gender"):
            genders[r["gender"]] = genders.get(r["gender"], 0) + 1
        statuses[r.get("status", "active")] = statuses.get(r.get("status", "active"), 0) + 1
    return {"total": total, "by_language": langs, "by_age_range": ages,
            "by_gender": genders, "by_status": statuses}


def _score(r: Dict, criteria: Dict) -> int:
    score = 1
    if criteria.get("language") and r.get("language") == criteria["language"]:
        score += 5
    if criteria.get("city") and r.get("city", "").lower() == criteria.get("city", "").lower():
        score += 3
    if criteria.get("age_range") and r.get("age_range") == criteria["age_range"]:
        score += 2
    if criteria.get("gender") and r.get("gender") == criteria["gender"]:
        score += 2
    if criteria.get("interests"):
        overlap = set(criteria["interests"]).intersection(set(r.get("interests", [])))
        score += len(overlap) * 2
    return score


def _update_respondent(respondent_id: str, data: Dict) -> Dict:
    doc_ref = db.collection(RESPONDENTS).document(respondent_id)
    r = doc_ref.get().to_dict()
    updatable = ["email", "city", "country", "age_range", "gender",
                 "interests", "whatsapp_number"]
    updates = {k: data[k] for k in updatable if k in data}
    updates["last_updated"] = datetime.now(timezone.utc).isoformat()
    sensitive = r.get("sensitive", {})
    if "sexual_orientation" in data:
        sensitive["sexual_orientation"] = data["sexual_orientation"]
    if "medical_conditions" in data:
        sensitive["medical_conditions"] = data["medical_conditions"]
    updates["sensitive"] = sensitive
    doc_ref.update(updates)
    return _safe_view({**r, **updates})
