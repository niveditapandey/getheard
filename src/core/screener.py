"""
Screener — pre-interview qualification system.

Each project can have a screener with:
  - Multiple-choice questions (single or multi-select)
  - Yes/No questions
  - Free-text questions (AI-evaluated)
  - Number/age range questions

Each question has qualifying criteria. A respondent must pass ALL
required questions to proceed to the interview.

Screener config is stored as project["screener"]:
{
  "enabled": true,
  "questions": [
    {
      "id": "sq1",
      "text": "Have you used a mobile banking app in the last 3 months?",
      "type": "single_choice",        # single_choice | multi_choice | yes_no | text
      "options": ["Yes", "No"],        # for choice questions
      "required_to_qualify": true,     # if false, question is informational only
      "qualifier": "include",          # include (must match) | exclude (must NOT match)
      "qualifying_answers": ["Yes"],   # answers that qualify (for choice questions)
      "ai_criteria": ""               # for text questions: what qualifies (natural language)
    }
  ],
  "disqualification_message": "Thank you for your time...",
  "qualification_message": "Great news — you qualify!",
  "quota": 0                           # 0 = unlimited; N = stop after N qualified
}
"""

import logging
from typing import Optional

from google import genai
from google.genai import types

from config.settings import settings

logger = logging.getLogger(__name__)

DEFAULT_DISQUALIFICATION_MESSAGE = (
    "Thank you so much for your time and interest. "
    "Unfortunately, you don't match the specific profile we're looking for in this study. "
    "We hope to include you in future research!"
)

DEFAULT_QUALIFICATION_MESSAGE = (
    "Great news — you qualify for this study! "
    "You'll now be connected with our AI interviewer. "
    "The conversation takes about 10–15 minutes."
)


# ── Answer evaluation ──────────────────────────────────────────────────────────

def _evaluate_choice(question: dict, answer) -> bool:
    """Evaluate a single/multi-choice or yes/no answer."""
    qualifying = {a.lower().strip() for a in question.get("qualifying_answers", [])}
    qualifier = question.get("qualifier", "include")

    if isinstance(answer, list):
        given = {a.lower().strip() for a in answer}
    else:
        given = {str(answer).lower().strip()}

    matched = bool(given & qualifying)
    return matched if qualifier == "include" else not matched


def _evaluate_text_with_ai(question: dict, answer: str) -> bool:
    """Use Gemini to evaluate whether a free-text answer qualifies."""
    criteria = question.get("ai_criteria", "").strip()
    if not criteria:
        return True  # No criteria defined — pass by default

    prompt = f"""You are evaluating a survey screener response.

Question: {question.get("text", "")}
Qualification criteria: {criteria}
Respondent's answer: {answer}

Does this answer meet the qualification criteria?
Reply with ONLY "YES" or "NO" — nothing else."""

    try:
        client = (
            genai.Client(api_key=settings.gemini_api_key)
            if settings.gemini_api_key
            else genai.Client(vertexai=True, project=settings.gcp_project_id, location=settings.gcp_location)
        )
        response = client.models.generate_content(
            model=settings.gemini_model,  # flash — fast and cheap for this
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=10),
        )
        result = response.text.strip().upper()
        return result.startswith("YES")
    except Exception as e:
        logger.warning(f"AI screener evaluation failed, defaulting to pass: {e}")
        return True


def evaluate_screener(screener_config: dict, answers: dict) -> dict:
    """
    Evaluate a set of screener answers against the config.

    Args:
        screener_config: The project's screener dict
        answers: {question_id: answer_value}

    Returns:
        {
            "qualified": bool,
            "failed_questions": [{"id": ..., "text": ...}],
            "message": str    # to show respondent
        }
    """
    questions = screener_config.get("questions", [])
    failed = []

    for q in questions:
        if not q.get("required_to_qualify", True):
            continue  # informational question, skip evaluation

        qid = q.get("id", "")
        answer = answers.get(qid)

        if answer is None or answer == "":
            # Unanswered required question = fail
            failed.append({"id": qid, "text": q.get("text", "")})
            continue

        qtype = q.get("type", "single_choice")

        if qtype in ("single_choice", "multi_choice", "yes_no"):
            passed = _evaluate_choice(q, answer)
        elif qtype == "text":
            passed = _evaluate_text_with_ai(q, str(answer))
        else:
            passed = True  # unknown type — pass

        if not passed:
            failed.append({"id": qid, "text": q.get("text", "")})

    qualified = len(failed) == 0

    if qualified:
        message = screener_config.get("qualification_message", DEFAULT_QUALIFICATION_MESSAGE)
    else:
        message = screener_config.get("disqualification_message", DEFAULT_DISQUALIFICATION_MESSAGE)

    return {
        "qualified": qualified,
        "failed_questions": failed,
        "message": message,
    }


# ── Screener generation ────────────────────────────────────────────────────────

SCREENER_GEN_PROMPT = """You are a qualitative research expert designing a pre-interview screener.

RESEARCH BRIEF:
- Project: {project_name}
- Research Type: {research_type}
- Target Audience: {audience}
- Objective: {objective}

Design {count} screener questions to qualify respondents for this study.
Focus on: usage recency, category involvement, age/demographics, and relevant experience.

Return ONLY valid JSON (no markdown):
{{
  "questions": [
    {{
      "id": "sq1",
      "text": "Question text",
      "type": "single_choice",
      "options": ["Option A", "Option B", "Option C"],
      "required_to_qualify": true,
      "qualifier": "include",
      "qualifying_answers": ["Option A"],
      "ai_criteria": ""
    }}
  ],
  "disqualification_message": "Thank you for your interest! Unfortunately, you don't match the profile we need for this study. We hope to include you in future research!",
  "qualification_message": "You qualify for this study! You'll now speak with our AI interviewer for about 10–15 minutes."
}}

Types available: single_choice (pick one), multi_choice (pick many), yes_no, text (AI-evaluated)
For text questions, set ai_criteria to what qualifies (natural language description).
For choice questions, set qualifying_answers to the list of answers that qualify.
qualifier: "include" means they must pick from qualifying_answers; "exclude" means they must NOT."""


def generate_screener_questions(
    project_name: str,
    research_type: str,
    audience: str,
    objective: str,
    count: int = 4,
) -> dict:
    """Use Gemini to auto-generate screener questions from a research brief."""
    import json

    prompt = SCREENER_GEN_PROMPT.format(
        project_name=project_name,
        research_type=research_type,
        audience=audience,
        objective=objective,
        count=count,
    )

    client = (
        genai.Client(api_key=settings.gemini_api_key)
        if settings.gemini_api_key
        else genai.Client(vertexai=True, project=settings.gcp_project_id, location=settings.gcp_location)
    )

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=2048,
            system_instruction="Return only valid JSON with no markdown or code fences.",
        ),
    )

    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    config = json.loads(raw)
    config["enabled"] = True
    config.setdefault("quota", 0)
    return config
