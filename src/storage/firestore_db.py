"""
Firestore database client — single shared instance for the whole app.
All storage modules import db from here.
"""
import os
from google.cloud import firestore

_db = None

def _get_db():
    global _db
    if _db is None:
        _project = os.environ.get("GCP_PROJECT_ID", "getheard-484014")
        _db = firestore.Client(project=_project, database="(default)")
    return _db

class _LazyDB:
    """Proxy that defers Firestore client creation until first use."""
    def __getattr__(self, name):
        return getattr(_get_db(), name)

db = _LazyDB()


# Collection names
PROJECTS     = "projects"
CLIENTS      = "clients"
RESPONDENTS  = "respondents"
PANELS       = "panels"
REPORTS      = "reports"
REDEMPTIONS  = "redemptions"
TRANSCRIPTS  = "transcripts"
POINTS       = "points"
