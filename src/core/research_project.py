"""
Research Project - manages project briefs, AI-generated questions, and session links.

A "project" = a research study with:
  - a brief (objective, audience, industry, etc.)
  - AI-generated + editable interview questions
  - linked interview transcripts
  - reports
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from google import genai
from google.genai import types

from config.settings import settings
from src.core.genai_client import get_genai_client
from src.storage.doc_store import DocStore
from src.storage.firestore_db import PROJECTS

logger = logging.getLogger(__name__)

PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

# Firestore-backed store (survives Cloud Run redeploys) with local fallback
_store = DocStore(PROJECTS, PROJECTS_DIR, id_field="project_id")

# Supported question counts
VALID_QUESTION_COUNTS = [5, 7, 10, 12, 15, 20, 25, 30]

RESEARCH_TYPES = {
    "cx":        "Customer Experience",
    "ux":        "User Experience / Product",
    "brand":     "Brand Perception",
    "product":   "Product Feedback",
    "nps":       "Net Promoter Score Deep-Dive",
    "employee":  "Employee Satisfaction",
    "market":    "Market Research",
    "custom":    "Custom / Other",
}

INDUSTRIES = [
    "Healthcare", "Retail / E-commerce", "Banking / Finance",
    "Telecom", "Food & Beverage", "Education", "Travel & Hospitality",
    "Government / Public Services", "Technology / SaaS", "Other",
]

LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi", "id": "Indonesian",
    "fil": "Filipino", "th": "Thai", "vi": "Vietnamese",
    "ko": "Korean", "ja": "Japanese", "zh": "Mandarin Chinese",
}


class ResearchProject:
    """Represents a single research study."""

    def __init__(self, data: dict):
        self._data = data

    # ── Accessors ──────────────────────────────────────────────────────────
    @property
    def project_id(self) -> str:
        return self._data["project_id"]

    @property
    def name(self) -> str:
        return self._data["name"]

    @property
    def questions(self) -> List[dict]:
        return self._data.get("questions", [])

    @property
    def language(self) -> str:
        return self._data.get("language", "en")

    @property
    def question_count(self) -> int:
        return len(self.questions)

    def to_dict(self) -> dict:
        return dict(self._data)

    # ── Mutation ───────────────────────────────────────────────────────────
    def update_questions(self, questions: List[dict]):
        self._data["questions"] = questions
        self._data["updated_at"] = datetime.now().isoformat()
        _save_project(self._data)

    def add_session(self, session_id: str):
        sessions = self._data.setdefault("sessions", [])
        if session_id not in sessions:
            sessions.append(session_id)
            self._data["interviews_completed"] = len(sessions)
            self._data["updated_at"] = datetime.now().isoformat()
            _save_project(self._data)


# ── Persistence (Firestore-backed via DocStore, local fallback) ──────────────

def _save_project(data: dict):
    _store.save(data["project_id"], data)


def get_project(project_id: str) -> Optional[ResearchProject]:
    data = _store.load(project_id)
    return ResearchProject(data) if data else None


def list_projects() -> List[dict]:
    results = []
    for data in _store.list_all():
        try:
            results.append({
                "project_id": data["project_id"],
                "name": data["name"],
                "research_type": data.get("research_type", ""),
                "language": data.get("language", "en"),
                "question_count": len(data.get("questions", [])),
                "sessions": len(data.get("sessions", [])),
                "created_at": data.get("created_at", ""),
                "status": data.get("status", "active"),
            })
        except Exception:
            pass
    # Newest first
    results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return results


def update_project_field(project_id: str, field: str, value) -> bool:
    """
    Update a single top-level field on a project. Returns True on success,
    False if the project doesn't exist.
    """
    return _store.update_field(project_id, field, value)


# ── AI Question Generation ─────────────────────────────────────────────────

QUESTION_GEN_PROMPT = """You are an expert qualitative research designer with 15 years of experience in voice-of-customer studies across Asia.

Generate {count} interview questions for the following research study. The questions will be asked by an AI interviewer over voice/WhatsApp.

RESEARCH BRIEF:
- Project Name: {name}
- Research Type: {research_type}
- Industry: {industry}
- Objective: {objective}
- Target Audience: {audience}
- Interview Language: {language}
- Key Topics to Explore: {topics}

REQUIREMENTS:
1. Questions must be open-ended and conversational (not yes/no)
2. Build from broad → specific (funnel structure)
3. Mix of: experience recall, emotional probes, satisfaction drivers, improvement areas
4. Culturally appropriate for {language} speakers
5. Each question should be standalone (no "as you mentioned" dependencies)
6. Include 1-2 follow-up probes per main question (optional, for AI to use if needed)
7. Match depth to question count: {count} questions = {depth_guidance}

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{{
  "questions": [
    {{
      "number": 1,
      "type": "opening|experience|emotional|satisfaction|improvement|closing",
      "main": "The main question text",
      "probe": "Optional follow-up probe if they give a short answer",
      "intent": "What insight this question aims to uncover"
    }}
  ]
}}"""

DEPTH_GUIDANCE = {
    5:  "very focused, each question must cover major ground",
    7:  "focused, prioritize 3 core topics",
    10: "moderate depth, balance breadth and depth",
    12: "moderate depth, can explore 4-5 distinct topics",
    15: "good depth, explore 5-6 topics with follow-ups",
    20: "deep exploration, 6-7 topics with rich follow-ups",
    25: "comprehensive, full journey mapping",
    30: "exhaustive research, complete journey with emotion mapping",
}


def generate_questions(
    name: str,
    research_type: str,
    industry: str,
    objective: str,
    audience: str,
    language: str,
    topics: str,
    count: int,
) -> List[dict]:
    """
    Use Gemini to generate interview questions based on the research brief.
    Returns list of question dicts.
    """
    if count not in VALID_QUESTION_COUNTS:
        count = min(VALID_QUESTION_COUNTS, key=lambda x: abs(x - count))

    client = get_genai_client()

    prompt = QUESTION_GEN_PROMPT.format(
        count=count,
        name=name,
        research_type=RESEARCH_TYPES.get(research_type, research_type),
        industry=industry,
        objective=objective,
        audience=audience,
        language=LANGUAGE_NAMES.get(language, language),
        topics=topics or "general experience, satisfaction, pain points, improvements",
        depth_guidance=DEPTH_GUIDANCE.get(count, "balanced depth"),
    )

    logger.info(f"Generating {count} questions for '{name}' ({research_type}/{language})")
    response = client.models.generate_content(
        model=settings.gemini_model_pro,  # pro — one-shot quality question generation
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=4096),
    )

    raw = response.text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"Gemini returned invalid JSON (first 300 chars): {raw[:300]}")
        raise ValueError("Gemini returned malformed JSON for question generation. Please try again.")

    questions = data.get("questions", [])
    if not questions:
        logger.warning(f"Gemini returned zero questions — raw: {raw[:200]}")
        raise ValueError("Gemini returned no questions. Please try again.")
    logger.info(f"Generated {len(questions)} questions")
    return questions


def create_project(
    name: str,
    research_type: str,
    industry: str,
    objective: str,
    audience: str,
    language: str,
    topics: str,
    question_count: int,
) -> ResearchProject:
    """Create a new research project with AI-generated questions."""
    project_id = str(uuid.uuid4())[:8]

    questions = generate_questions(
        name=name,
        research_type=research_type,
        industry=industry,
        objective=objective,
        audience=audience,
        language=language,
        topics=topics,
        count=question_count,
    )

    data = {
        "project_id": project_id,
        "name": name,
        "research_type": research_type,
        "industry": industry,
        "objective": objective,
        "audience": audience,
        "language": language,
        "topics": topics,
        "question_count": question_count,
        "questions": questions,
        "sessions": [],
        # Study lifecycle
        "status": "briefing",
        "pipeline": {
            "briefing": {"status": "completed", "completed_at": datetime.now().isoformat()},
        },
        # Client linkage
        "client_id": None,
        "client_email": None,
        # Geography & panel
        "market": "IN",
        "target_respondents": 10,
        # Interview progress
        "interviews_completed": 0,
        # Payment
        "payment_received": False,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    _save_project(data)
    logger.info(f"Project {project_id} created: '{name}'")
    return ResearchProject(data)
