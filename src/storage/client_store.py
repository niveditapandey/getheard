"""
client_store.py — JSON persistence for GetHeard client accounts.

Each client stored as clients/{client_id}.json
"""
import hashlib
import json
import logging
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
CLIENTS_DIR = BASE_DIR / "clients"
CLIENTS_DIR.mkdir(exist_ok=True)


def _client_path(client_id: str) -> Path:
    return CLIENTS_DIR / f"{client_id}.json"


def _hash_password(password: str) -> str:
    """Simple SHA-256 hash with salt. Replace with bcrypt in production."""
    salt = "getheard-salt-2026"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def create_client(data: Dict[str, Any]) -> Dict:
    """Register a new client. Raises ValueError on duplicate email or missing fields."""
    required = {"name", "email", "company", "country", "password"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Missing fields: {missing}")

    email = str(data["email"]).strip().lower()
    if _find_by_email(email):
        raise ValueError("An account with this email already exists.")

    client_id = str(uuid.uuid4())[:8]
    client = {
        "client_id":    client_id,
        "name":         str(data["name"]).strip(),
        "email":        email,
        "company":      str(data["company"]).strip(),
        "country":      str(data["country"]).strip(),
        "password_hash": _hash_password(str(data["password"])),
        "status":       "active",
        "created_at":   datetime.now(timezone.utc).isoformat(),
        "last_login":   None,
        "studies":      [],
    }
    _client_path(client_id).write_text(json.dumps(client, indent=2, ensure_ascii=False))
    logger.info(f"Client created: {client_id} ({email})")
    return _safe_view(client)


def authenticate_client(email: str, password: str) -> Optional[Dict]:
    """Returns client (safe view) if credentials match, else None."""
    client = _find_by_email(email.strip().lower())
    if not client:
        return None
    if client.get("password_hash") != _hash_password(password):
        return None
    # Update last login
    client["last_login"] = datetime.now(timezone.utc).isoformat()
    _client_path(client["client_id"]).write_text(json.dumps(client, indent=2, ensure_ascii=False))
    return _safe_view(client)


def get_client(client_id: str) -> Optional[Dict]:
    path = _client_path(client_id)
    if not path.exists():
        return None
    return _safe_view(json.loads(path.read_text(encoding="utf-8")))


def list_clients() -> List[Dict]:
    clients = []
    for p in CLIENTS_DIR.glob("*.json"):
        try:
            clients.append(_safe_view(json.loads(p.read_text(encoding="utf-8"))))
        except Exception:
            pass
    clients.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return clients


def add_study_to_client(client_id: str, project_id: str) -> bool:
    path = _client_path(client_id)
    if not path.exists():
        return False
    c = json.loads(path.read_text(encoding="utf-8"))
    if project_id not in c.get("studies", []):
        c.setdefault("studies", []).append(project_id)
        path.write_text(json.dumps(c, indent=2, ensure_ascii=False))
    return True


def _safe_view(client: Dict) -> Dict:
    v = dict(client)
    v.pop("password_hash", None)
    return v


def _find_by_email(email: str) -> Optional[Dict]:
    for p in CLIENTS_DIR.glob("*.json"):
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
            if c.get("email") == email:
                return c
        except Exception:
            pass
    return None
