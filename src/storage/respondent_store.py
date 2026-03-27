"""
Respondent store — JSON persistence for the GetHeard respondent panel database.

Each respondent is stored as respondents/{respondent_id}.json.
Sensitive fields (sexual_orientation, medical_conditions) are kept in a
separate 'sensitive' sub-dict and never surfaced in list queries unless
the caller explicitly requests them.
"""

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
RESPONDENTS_DIR = BASE_DIR / "respondents"
RESPONDENTS_DIR.mkdir(exist_ok=True)


# ── Schema ────────────────────────────────────────────────────────────────────

REQUIRED_FIELDS = {"name", "phone", "language", "consent_contact"}

AGE_RANGES    = ["18-24", "25-34", "35-44", "45-54", "55+"]
GENDERS       = ["male", "female", "non_binary", "prefer_not_to_say", "other"]
ORIENTATIONS  = ["heterosexual", "gay_lesbian", "bisexual", "prefer_not_to_say", "other"]
MARITAL       = ["single", "married", "separated", "divorced", "widowed", "prefer_not_to_say"]
LANGUAGES     = ["en", "hi", "id", "fil", "th", "vi", "ko", "ja", "zh"]
INTERESTS     = ["fintech", "ecommerce", "food", "travel", "healthcare",
                 "education", "tech", "real_estate", "insurance", "gaming"]


def _clean_phone(raw: str) -> str:
    """Normalise phone to E.164-ish format (keep digits and leading +)."""
    digits = re.sub(r"[^\d+]", "", raw.strip())
    if digits and not digits.startswith("+"):
        digits = "+" + digits
    return digits


def _respondent_path(respondent_id: str) -> Path:
    return RESPONDENTS_DIR / f"{respondent_id}.json"


# ── CRUD ──────────────────────────────────────────────────────────────────────

def enroll_respondent(data: Dict[str, Any]) -> Dict:
    """
    Validate and persist a new respondent.
    Returns the saved respondent dict (without sensitive sub-dict in the top level).
    Raises ValueError on validation failure.
    """
    # Required fields
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    if not data.get("consent_contact"):
        raise ValueError("Respondent must consent to be contacted.")

    phone = _clean_phone(str(data.get("phone", "")))
    if len(phone) < 7:
        raise ValueError("Invalid phone number.")

    # De-duplicate by phone
    existing = _find_by_phone(phone)
    if existing:
        logger.info(f"Re-enrollment detected for phone {phone[:6]}*** → updating")
        return _update_respondent(existing["respondent_id"], data)

    respondent_id = str(uuid.uuid4())[:8]

    respondent = {
        "respondent_id":    respondent_id,
        "name":             str(data["name"]).strip(),
        "phone":            phone,
        "whatsapp_number":  _clean_phone(str(data.get("whatsapp_number", phone))),
        "voice_number":     _clean_phone(str(data.get("voice_number", phone))),
        "email":            str(data.get("email", "")).strip().lower() or None,
        "language":         data.get("language", "en"),
        "city":             str(data.get("city", "")).strip() or None,
        "country":          str(data.get("country", "")).strip() or None,
        "age_range":        data.get("age_range"),
        "gender":           data.get("gender"),
        "marital_status":   data.get("marital_status"),
        "occupation":       str(data.get("occupation", "")).strip() or None,
        "interests":        data.get("interests", []),
        "consent_contact":  bool(data.get("consent_contact", False)),
        "enrolled_at":      datetime.now(timezone.utc).isoformat(),
        "last_updated":     datetime.now(timezone.utc).isoformat(),
        "source":           data.get("source", "web_form"),
        "status":           "active",
        "interviews_completed": 0,
        "last_interviewed_at":  None,
        # Sensitive fields stored separately — only accessible via get_respondent_full()
        "sensitive": {
            "sexual_orientation": data.get("sexual_orientation"),
            "medical_conditions": str(data.get("medical_conditions", "")).strip() or None,
        },
    }

    _respondent_path(respondent_id).write_text(
        json.dumps(respondent, indent=2, ensure_ascii=False)
    )
    logger.info(f"Respondent enrolled: {respondent_id} ({respondent['language']})")
    return _safe_view(respondent)


def get_respondent(respondent_id: str) -> Optional[Dict]:
    """Return respondent without sensitive fields."""
    path = _respondent_path(respondent_id)
    if not path.exists():
        return None
    return _safe_view(json.loads(path.read_text(encoding="utf-8")))


def get_respondent_full(respondent_id: str) -> Optional[Dict]:
    """Return complete respondent including sensitive fields (internal use only)."""
    path = _respondent_path(respondent_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def update_respondent_status(respondent_id: str, status: str) -> bool:
    path = _respondent_path(respondent_id)
    if not path.exists():
        return False
    r = json.loads(path.read_text(encoding="utf-8"))
    r["status"] = status
    r["last_updated"] = datetime.now(timezone.utc).isoformat()
    if status == "interviewed":
        r["interviews_completed"] = r.get("interviews_completed", 0) + 1
        r["last_interviewed_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(r, indent=2, ensure_ascii=False))
    return True


def list_respondents(filters: Optional[Dict] = None) -> List[Dict]:
    """
    List active respondents, optionally filtered.
    Supported filter keys: language, city, age_range, gender, status, interests (list).
    Returns safe views (no sensitive fields).
    """
    results = []
    for p in RESPONDENTS_DIR.glob("*.json"):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
            if filters and not _matches(r, filters):
                continue
            results.append(_safe_view(r))
        except Exception:
            pass
    return results


def search_respondents(criteria: Dict) -> List[Dict]:
    """
    Search respondents by criteria and return ranked matches.
    Criteria keys: language, city, age_range, gender, interests (list),
                   exclude_ids (list of respondent_ids to skip),
                   not_interviewed_days (int — skip recently interviewed)
    """
    all_r = []
    exclude = set(criteria.get("exclude_ids", []))
    for p in RESPONDENTS_DIR.glob("*.json"):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
            if r["respondent_id"] in exclude:
                continue
            if r.get("status") not in ("active", None):
                continue
            score = _score(r, criteria)
            if score > 0:
                all_r.append((_safe_view(r), score))
        except Exception:
            pass
    all_r.sort(key=lambda x: x[1], reverse=True)
    return [r for r, _ in all_r]


def get_stats() -> Dict:
    """Aggregate counts for the panel dashboard."""
    total = by_lang = by_age = by_gender = by_status = 0
    langs: Dict[str, int] = {}
    ages: Dict[str, int] = {}
    genders: Dict[str, int] = {}
    statuses: Dict[str, int] = {}

    for p in RESPONDENTS_DIR.glob("*.json"):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
            total += 1
            langs[r.get("language","?")] = langs.get(r.get("language","?"), 0) + 1
            if r.get("age_range"):
                ages[r["age_range"]] = ages.get(r["age_range"], 0) + 1
            if r.get("gender"):
                genders[r["gender"]] = genders.get(r["gender"], 0) + 1
            statuses[r.get("status","active")] = statuses.get(r.get("status","active"), 0) + 1
        except Exception:
            pass

    return {
        "total": total,
        "by_language": langs,
        "by_age_range": ages,
        "by_gender": genders,
        "by_status": statuses,
    }


# ── Private helpers ───────────────────────────────────────────────────────────

def _safe_view(r: Dict) -> Dict:
    """Strip sensitive sub-dict from a respondent record."""
    v = dict(r)
    v.pop("sensitive", None)
    return v


def _matches(r: Dict, filters: Dict) -> bool:
    for k, v in filters.items():
        if k == "interests":
            if not set(v).intersection(set(r.get("interests", []))):
                return False
        elif k == "status":
            if r.get("status") != v:
                return False
        elif r.get(k) and r.get(k) != v:
            return False
    return True


def _score(r: Dict, criteria: Dict) -> int:
    """Score a respondent against search criteria. Higher = better match."""
    score = 1  # base — any active respondent gets 1
    if criteria.get("language") and r.get("language") == criteria["language"]:
        score += 5
    if criteria.get("city") and r.get("city", "").lower() == criteria["city"].lower():
        score += 3
    if criteria.get("age_range") and r.get("age_range") == criteria["age_range"]:
        score += 2
    if criteria.get("gender") and r.get("gender") == criteria["gender"]:
        score += 2
    if criteria.get("interests"):
        overlap = set(criteria["interests"]).intersection(set(r.get("interests", [])))
        score += len(overlap) * 2
    # Deprioritise recently interviewed
    if criteria.get("not_interviewed_days") and r.get("last_interviewed_at"):
        from datetime import timedelta
        days_ago = (datetime.now(timezone.utc) - datetime.fromisoformat(
            r["last_interviewed_at"]
        )).days
        if days_ago < criteria["not_interviewed_days"]:
            score -= 10
    return score


def _find_by_phone(phone: str) -> Optional[Dict]:
    for p in RESPONDENTS_DIR.glob("*.json"):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
            if r.get("phone") == phone or r.get("whatsapp_number") == phone:
                return r
        except Exception:
            pass
    return None


def _update_respondent(respondent_id: str, data: Dict) -> Dict:
    path = _respondent_path(respondent_id)
    r = json.loads(path.read_text(encoding="utf-8"))
    updatable = ["email", "city", "country", "age_range", "gender", "marital_status",
                 "occupation", "interests", "whatsapp_number", "voice_number"]
    for k in updatable:
        if k in data:
            r[k] = data[k]
    r["last_updated"] = datetime.now(timezone.utc).isoformat()
    if "sexual_orientation" in data or "medical_conditions" in data:
        r.setdefault("sensitive", {})
        if "sexual_orientation" in data:
            r["sensitive"]["sexual_orientation"] = data["sexual_orientation"]
        if "medical_conditions" in data:
            r["sensitive"]["medical_conditions"] = data["medical_conditions"]
    path.write_text(json.dumps(r, indent=2, ensure_ascii=False))
    return _safe_view(r)
