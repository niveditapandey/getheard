"""
genai_client.py — Single source of truth for creating a Gemini client.

Routing:
    prefer_vertex=True  (default) → Vertex AI, billing to GCP credits.
                                     Falls back to the AI Studio key if Vertex
                                     init fails and a key is configured.
    prefer_vertex=False           → AI Studio key if set, else Vertex.

Centralising this means switching billing/auth is a one-line config change
(PREFER_VERTEX env var) rather than editing a dozen call sites.
"""

import logging
from google import genai

from config.settings import settings

logger = logging.getLogger(__name__)


def get_genai_client() -> genai.Client:
    """Return a configured Gemini client per the routing rules above."""
    use_vertex = settings.prefer_vertex or not settings.gemini_api_key
    if use_vertex:
        try:
            return genai.Client(
                vertexai=True,
                project=settings.gcp_project_id,
                location=settings.gcp_location,
            )
        except Exception as e:
            if settings.gemini_api_key:
                logger.warning(f"Vertex client init failed, falling back to AI Studio key: {e}")
                return genai.Client(api_key=settings.gemini_api_key)
            raise
    return genai.Client(api_key=settings.gemini_api_key)
