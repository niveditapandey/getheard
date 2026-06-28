"""
job_store.py — Firestore-backed async job records.

Tracks long-running work (e.g. report generation) so it can run off the request
path via Cloud Tasks and be polled for status.

Status lifecycle: queued → running → done | error
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from src.storage.firestore_db import db, JOBS

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job(job_type: str, params: dict) -> str:
    """Create a queued job and return its id."""
    job_id = uuid.uuid4().hex[:12]
    db.collection(JOBS).document(job_id).set({
        "job_id":     job_id,
        "type":       job_type,
        "status":     "queued",
        "params":     params or {},
        "result":     None,
        "error":      None,
        "created_at": _now(),
        "updated_at": _now(),
    })
    logger.info(f"[job {job_id}] created ({job_type})")
    return job_id


def get_job(job_id: str) -> Optional[Dict]:
    doc = db.collection(JOBS).document(job_id).get()
    return doc.to_dict() if doc.exists else None


def _update(job_id: str, **fields) -> None:
    fields["updated_at"] = _now()
    db.collection(JOBS).document(job_id).update(fields)


def set_running(job_id: str) -> None:
    _update(job_id, status="running")
    logger.info(f"[job {job_id}] running")


def set_done(job_id: str, result: dict) -> None:
    _update(job_id, status="done", result=result)
    logger.info(f"[job {job_id}] done")


def set_error(job_id: str, error: str) -> None:
    _update(job_id, status="error", error=str(error)[:1000])
    logger.warning(f"[job {job_id}] error: {error}")
