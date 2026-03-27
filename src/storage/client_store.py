"""
client_store.py — Firestore persistence for GetHeard client accounts.
Collection: clients/{client_id}
"""
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.storage.firestore_db import db, CLIENTS

logger = logging.getLogger(__name__)

SALT = "getheard-salt-2026"


def _hash_password(password: str) -> str:
    return hashlib.sha256(f"{SALT}{password}".encode()).hexdigest()


def _safe_view(client: Dict) -> Dict:
    v = dict(client)
    v.pop("password_hash", None)
    return v


def _find_by_email(email: str) -> Optional[Dict]:
    docs = db.collection(CLIENTS).where("email", "==", email).limit(1).stream()
    for doc in docs:
        return doc.to_dict()
    return None


def create_client(data: Dict[str, Any]) -> Dict:
    required = {"name", "email", "company", "country", "password"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Missing fields: {missing}")

    email = str(data["email"]).strip().lower()
    if _find_by_email(email):
        raise ValueError("An account with this email already exists.")

    client_id = str(uuid.uuid4())[:8]
    client = {
        "client_id":     client_id,
        "name":          str(data["name"]).strip(),
        "email":         email,
        "company":       str(data["company"]).strip(),
        "country":       str(data["country"]).strip(),
        "password_hash": _hash_password(str(data["password"])),
        "status":        "active",
        "created_at":    datetime.now(timezone.utc).isoformat(),
        "last_login":    None,
        "studies":       [],
    }
    db.collection(CLIENTS).document(client_id).set(client)
    logger.info(f"Client created: {client_id} ({email})")
    return _safe_view(client)


def authenticate_client(email: str, password: str) -> Optional[Dict]:
    client = _find_by_email(email.strip().lower())
    if not client:
        return None
    if client.get("password_hash") != _hash_password(password):
        return None
    client["last_login"] = datetime.now(timezone.utc).isoformat()
    db.collection(CLIENTS).document(client["client_id"]).update(
        {"last_login": client["last_login"]}
    )
    return _safe_view(client)


def get_client(client_id: str) -> Optional[Dict]:
    doc = db.collection(CLIENTS).document(client_id).get()
    if not doc.exists:
        return None
    return _safe_view(doc.to_dict())


def list_clients() -> List[Dict]:
    docs = db.collection(CLIENTS).order_by(
        "created_at", direction="DESCENDING"
    ).stream()
    return [_safe_view(d.to_dict()) for d in docs]


def add_study_to_client(client_id: str, project_id: str) -> bool:
    doc_ref = db.collection(CLIENTS).document(client_id)
    doc = doc_ref.get()
    if not doc.exists:
        return False
    c = doc.to_dict()
    studies = c.get("studies", [])
    if project_id not in studies:
        studies.append(project_id)
        doc_ref.update({"studies": studies})
    return True
