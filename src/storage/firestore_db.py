"""
Firestore database client — single shared instance for the whole app.
All storage modules import db from here.
"""
from google.cloud import firestore

# Single shared Firestore client
# On Cloud Run: authenticates automatically via the service account
# Locally: uses application default credentials (gcloud auth application-default login)
db = firestore.Client(project="getheard-484014", database="(default)")

# Collection names
PROJECTS     = "projects"
CLIENTS      = "clients"
RESPONDENTS  = "respondents"
PANELS       = "panels"
REPORTS      = "reports"
REDEMPTIONS  = "redemptions"
TRANSCRIPTS  = "transcripts"
POINTS       = "points"
