"""
mission_index.py — Retrieval index for Mission Control (Firestore vector search).

Reports and transcripts are chunked, embedded (Vertex text-embedding-004), and
stored in the `mission_chunks` Firestore collection with a vector field. At query
time we embed the question and use Firestore find_nearest() to pull the most
relevant chunks across all studies — so Mission Control scales past the Gemini
context window.

All writes are best-effort: indexing failures never break report/transcript saves.
Requires a Firestore vector index on `mission_chunks.embedding` (see deploy docs).
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Optional

from src.storage.firestore_db import db, MISSION_CHUNKS
from src.core.embeddings import embed_text

logger = logging.getLogger(__name__)


def _vector(values: List[float]):
    from google.cloud.firestore_v1.vector import Vector
    return Vector(values)


def _chunk_id(source_id: str, kind: str, idx: int) -> str:
    return hashlib.md5(f"{source_id}:{kind}:{idx}".encode()).hexdigest()[:16]


def _save_chunk(chunk_id: str, text: str, meta: dict) -> bool:
    emb = embed_text(text)
    if emb is None:
        return False
    doc = {
        "text": text[:2000],
        "embedding": _vector(emb),
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        **meta,
    }
    db.collection(MISSION_CHUNKS).document(chunk_id).set(doc)
    return True


# ── Indexing ────────────────────────────────────────────────────────────────

def index_report(report: dict) -> int:
    """Chunk a report into retrievable pieces and index them. Returns chunk count."""
    try:
        rid = report.get("report_id") or report.get("project_id") or ""
        pid = report.get("project_id", "")
        pname = report.get("project_name", "Unknown")
        base = {"source_type": "report", "report_id": rid, "project_id": pid, "project_name": pname}

        texts: List[str] = []
        if report.get("executive_summary"):
            texts.append(f"Executive summary: {report['executive_summary']}")
        for t in (report.get("key_themes") or []):
            s = t.get("theme") if isinstance(t, dict) else t
            if s:
                texts.append(f"Theme: {s}")
        for p in (report.get("pain_points") or []):
            s = p.get("pain_point") if isinstance(p, dict) else p
            if s:
                texts.append(f"Pain point: {s}")
        for r in (report.get("recommendations") or []):
            s = r.get("recommendation") if isinstance(r, dict) else r
            if s:
                texts.append(f"Recommendation: {s}")
        for q in (report.get("notable_quotes") or []):
            s = q.get("quote") if isinstance(q, dict) else q
            if s:
                texts.append(f"Quote: {s}")

        n = 0
        for i, txt in enumerate(texts):
            if _save_chunk(_chunk_id(rid, "report", i), txt, base):
                n += 1
        logger.info(f"Indexed report {rid}: {n} chunks")
        return n
    except Exception as e:
        logger.warning(f"index_report failed: {e}")
        return 0


def index_transcript(transcript: dict) -> int:
    """Index a transcript's respondent turns. Returns chunk count."""
    try:
        sid = transcript.get("session_id", "")
        pid = transcript.get("project_id") or transcript.get("metadata", {}).get("project_id", "")
        lang = transcript.get("language_code", "en")
        pname = ""
        if pid:
            try:
                from src.core.research_project import get_project
                proj = get_project(pid)
                pname = proj.name if proj else ""
            except Exception:
                pass
        base = {"source_type": "transcript", "session_id": sid, "project_id": pid,
                "project_name": pname, "lang": lang}

        # Group respondent turns into ~3-turn chunks for richer context
        turns = [t.get("text", "").strip()
                 for t in transcript.get("conversation", [])
                 if t.get("speaker") == "respondent" and t.get("text", "").strip()]
        n = 0
        for i in range(0, len(turns), 3):
            txt = " ".join(turns[i:i + 3])
            if txt and _save_chunk(_chunk_id(sid, "transcript", i), txt, base):
                n += 1
        logger.info(f"Indexed transcript {sid}: {n} chunks")
        return n
    except Exception as e:
        logger.warning(f"index_transcript failed: {e}")
        return 0


# ── Retrieval ───────────────────────────────────────────────────────────────

def search(query: str, k: int = 20) -> List[dict]:
    """Return the top-k most relevant chunks for a query. [] on any failure."""
    qemb = embed_text(query)
    if qemb is None:
        return []
    try:
        from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
        col = db.collection(MISSION_CHUNKS)
        results = col.find_nearest(
            vector_field="embedding",
            query_vector=_vector(qemb),
            distance_measure=DistanceMeasure.COSINE,
            limit=k,
        ).get()
        out = []
        for doc in results:
            d = doc.to_dict() or {}
            d.pop("embedding", None)  # don't ship the vector back
            out.append(d)
        return out
    except Exception as e:
        logger.warning(f"Vector search unavailable ({e}); caller should fall back")
        return []


def backfill() -> dict:
    """Index all existing reports and transcripts. Returns counts."""
    from src.core.report_generator import list_reports, load_report
    from src.storage.transcript import TranscriptManager

    reports = chunks_r = 0
    for meta in list_reports():
        full = load_report(meta["report_id"])
        if full:
            chunks_r += index_report(full)
            reports += 1

    tm = TranscriptManager()
    transcripts = chunks_t = 0
    for meta in tm.list_transcripts():
        full = tm.load(meta["session_id"])
        if full:
            chunks_t += index_transcript(full)
            transcripts += 1

    return {"reports": reports, "report_chunks": chunks_r,
            "transcripts": transcripts, "transcript_chunks": chunks_t}
