"""
Firestore database client — single shared instance for the whole app.
All storage modules import db from here.
"""
import os
from google.cloud import firestore

_project = os.environ.get("GCP_PROJECT_ID", "getheard-484014")
db = firestore.Client(project=_project, database="(default)")

# Collection names
PROJECTS     = "projects"
CLIENTS      = "clients"
RESPONDENTS  = "respondents"
PANELS       = "panels"
REPORTS      = "reports"
REDEMPTIONS  = "redemptions"
TRANSCRIPTS  = "transcripts"
POINTS       = "points"
