"""
embeddings.py — Text embeddings via Vertex AI (text-embedding-004, 768-dim).

Used by Mission Control's retrieval layer. Bills to GCP credits through the
shared Gemini client. embed_text() returns None on failure so callers can
degrade gracefully.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

EMBED_MODEL = "text-embedding-004"
EMBED_DIM = 768


def embed_text(text: str) -> Optional[List[float]]:
    """Embed a single string. Returns a 768-dim vector, or None on failure."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        from src.core.genai_client import get_genai_client
        client = get_genai_client()
        resp = client.models.embed_content(model=EMBED_MODEL, contents=text[:8000])
        return list(resp.embeddings[0].values)
    except Exception as e:
        logger.warning(f"Embedding failed: {e}")
        return None
