"""
doc_store.py — Firestore-backed JSON document store with a local-file fallback.

Why this exists:
    Projects, reports, and panels were originally persisted as local JSON files.
    On Cloud Run (no persistent disk) those files are wiped on every redeploy,
    silently losing all studies and reports. This store writes them to Firestore
    (which survives redeploys and bills to GCP credits) while keeping a best-effort
    local copy as a cache/backup so dev and tests keep working offline.

Behaviour:
    save(id, data)       → write to Firestore (primary); mirror to local (best effort)
    load(id)             → Firestore first; fall back to local file
    list_all()           → union of Firestore docs + local files (Firestore wins on dup)
    update_field(id,k,v) → load → mutate one key → save
    exists(id)           → load() is not None

If Firestore is unreachable (no creds locally), every operation degrades to the
local file path so the app still runs.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class DocStore:
    def __init__(self, collection: str, local_dir: Path, id_field: str = "id"):
        self.collection = collection
        self.local_dir = Path(local_dir)
        self.id_field = id_field  # the dict key that holds this doc's id (e.g. project_id)
        self.local_dir.mkdir(parents=True, exist_ok=True)

    def _doc_id(self, data: dict, fallback: str = "") -> str:
        """Derive the document id from a record using this store's id field."""
        return str(data.get(self.id_field) or fallback)

    # ── internals ──────────────────────────────────────────────────────────
    def _col(self):
        """Lazily resolve the Firestore collection; None if unavailable."""
        try:
            from src.storage.firestore_db import db
            return db.collection(self.collection)
        except Exception as e:  # missing creds, offline, etc.
            logger.warning(f"[{self.collection}] Firestore unavailable, using local files: {e}")
            return None

    def _local_path(self, doc_id: str) -> Path:
        return self.local_dir / f"{doc_id}.json"

    def _write_local(self, doc_id: str, data: dict) -> None:
        try:
            self._local_path(doc_id).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.debug(f"[{self.collection}] local mirror write failed for {doc_id}: {e}")

    # ── public API ─────────────────────────────────────────────────────────
    def save(self, doc_id: str, data: dict) -> None:
        col = self._col()
        wrote_firestore = False
        if col is not None:
            try:
                col.document(doc_id).set(data)
                wrote_firestore = True
            except Exception as e:
                logger.error(f"[{self.collection}] Firestore save failed for {doc_id}: {e}")
        # Always keep a local copy (backup in prod, primary in offline dev)
        self._write_local(doc_id, data)
        if not wrote_firestore:
            logger.warning(f"[{self.collection}] {doc_id} saved to local only (Firestore unavailable)")

    def load(self, doc_id: str) -> Optional[dict]:
        col = self._col()
        if col is not None:
            try:
                doc = col.document(doc_id).get()
                if doc.exists:
                    return doc.to_dict()
            except Exception as e:
                logger.warning(f"[{self.collection}] Firestore load failed for {doc_id}: {e}")
        # Fallback to local
        path = self._local_path(doc_id)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"[{self.collection}] corrupt local file {doc_id}: {e}")
        return None

    def exists(self, doc_id: str) -> bool:
        return self.load(doc_id) is not None

    def list_all(self) -> List[dict]:
        """Return every document as a dict. Firestore + local, deduped by id."""
        by_id: Dict[str, dict] = {}

        # Local first so Firestore can overwrite (Firestore is source of truth)
        for f in self.local_dir.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                by_id[self._doc_id(d, f.stem)] = d
            except Exception:
                continue

        col = self._col()
        if col is not None:
            try:
                for doc in col.stream():
                    d = doc.to_dict() or {}
                    by_id[doc.id] = d
            except Exception as e:
                logger.warning(f"[{self.collection}] Firestore list failed: {e}")

        return list(by_id.values())

    def update_field(self, doc_id: str, field: str, value) -> bool:
        data = self.load(doc_id)
        if data is None:
            return False
        data[field] = value
        data["updated_at"] = datetime.now().isoformat()
        self.save(doc_id, data)
        return True

    def migrate_local_to_firestore(self) -> int:
        """One-time: push any local files not yet in Firestore. Returns count migrated."""
        col = self._col()
        if col is None:
            logger.warning(f"[{self.collection}] cannot migrate — Firestore unavailable")
            return 0
        migrated = 0
        for f in self.local_dir.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                doc_id = self._doc_id(d, f.stem)
                snap = col.document(doc_id).get()
                if not snap.exists:
                    col.document(doc_id).set(d)
                    migrated += 1
                    logger.info(f"[{self.collection}] migrated {doc_id} → Firestore")
            except Exception as e:
                logger.error(f"[{self.collection}] migrate failed for {f.name}: {e}")
        return migrated
