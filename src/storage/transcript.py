"""
transcript.py — Firestore persistence for interview transcripts.
Collection: transcripts/{session_id}
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.storage.firestore_db import db, TRANSCRIPTS

logger = logging.getLogger(__name__)


class TranscriptManager:
    """Manages saving and loading of interview transcripts via Firestore."""

    def save(
        self,
        session_id: str,
        language_code: str,
        conversation: List[Dict],
        metadata: Optional[Dict] = None,
    ) -> str:
        """Save interview transcript to Firestore. Returns session_id."""
        data = {
            "session_id":    session_id,
            "language_code": language_code,
            "started_at":    metadata.get("started_at") if metadata else None,
            "ended_at":      datetime.now(timezone.utc).isoformat(),
            "metadata":      metadata or {},
            "conversation":  conversation,
            "turn_count":    len(conversation),
            "saved_at":      datetime.now(timezone.utc).isoformat(),
        }
        db.collection(TRANSCRIPTS).document(session_id).set(data)
        logger.info(f"Transcript saved to Firestore: {session_id}")
        return session_id

    def load(self, session_id: str) -> Optional[Dict]:
        """Load transcript by session_id."""
        doc = db.collection(TRANSCRIPTS).document(session_id).get()
        return doc.to_dict() if doc.exists else None

    def update_quality(self, session_id: str, quality: dict) -> None:
        """Persist quality score fields onto an existing transcript document."""
        db.collection(TRANSCRIPTS).document(session_id).update({
            "quality_score":  quality.get("score"),
            "quality_label":  quality.get("label"),
            "quality_flags":  quality.get("flags", []),
            "quality_details": quality.get("details", {}),
            "quality_ai_summary": quality.get("ai_summary"),
        })
        logger.info(f"Quality score saved for {session_id}: {quality.get('score')} ({quality.get('label')})")

    def list_transcripts(self) -> List[Dict]:
        """List all saved transcripts with summary metadata."""
        docs = db.collection(TRANSCRIPTS).order_by(
            "saved_at", direction="DESCENDING"
        ).stream()
        results = []
        for doc in docs:
            d = doc.to_dict()
            results.append({
                "session_id":    d.get("session_id"),
                "language_code": d.get("language_code"),
                "ended_at":      d.get("ended_at"),
                "turn_count":    d.get("turn_count", 0),
                "project_id":    d.get("metadata", {}).get("project_id"),
                "quality_score": d.get("quality_score"),
                "quality_label": d.get("quality_label"),
            })
        return results
