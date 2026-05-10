"""
Research Agent — natural-language query engine over GetHeard reports and transcripts.

Lets clients ask questions like:
  "Show all quotes where users mentioned trust"
  "Compare sentiment between Hindi and English respondents"
  "Which pain points were most common among the 25-34 age group?"
  "What quick wins can we implement this sprint?"
  "Summarise the emotional journey in 3 bullet points"

The agent loads the full report context + raw transcripts, then uses Gemini Pro
to answer with cited evidence.
"""

import json
import logging
from typing import Optional

from google import genai
from google.genai import types

from config.settings import settings
from src.core.report_generator import load_report
from src.storage.transcript import TranscriptManager

logger = logging.getLogger(__name__)


AGENT_SYSTEM = """You are a senior qualitative research analyst assistant embedded inside a research platform.
You have access to a completed research report AND the raw interview transcripts.
Your job is to answer the client's question accurately, citing specific evidence.

Rules:
1. Ground every answer in the data — quote directly from transcripts or the report.
2. Be concise but complete. Use bullet points where helpful.
3. Always include at least 2-3 verbatim quotes as evidence when available.
4. If the data doesn't support an answer, say so clearly — never fabricate.
5. Format your response as clean, readable text (use **bold** for emphasis, bullet points).
6. End every response with a "Sources" section listing the quoted evidence."""


AGENT_PROMPT = """RESEARCH REPORT:
{report_json}

RAW TRANSCRIPTS (selected relevant turns):
{transcripts_text}

CLIENT QUESTION: {query}

Answer the question based on the report and transcripts above. Cite specific quotes."""


def _extract_relevant_turns(transcripts: list, query: str, max_turns: int = 60) -> str:
    """Extract the most relevant transcript turns for the query context."""
    all_turns = []
    for i, t in enumerate(transcripts, 1):
        lang = t.get("language_code", "en")
        for turn in t.get("conversation", []):
            if turn.get("speaker") == "respondent" and turn.get("text"):
                all_turns.append({
                    "interview": i,
                    "lang": lang,
                    "text": turn["text"],
                    "q_idx": turn.get("question_idx", -1),
                })

    # For short datasets take all; for large ones take a spread
    if len(all_turns) <= max_turns:
        selected = all_turns
    else:
        step = max(1, len(all_turns) // max_turns)
        selected = all_turns[::step][:max_turns]

    lines = []
    for t in selected:
        lines.append(f"[Interview {t['interview']} | {t['lang']}] {t['text']}")
    return "\n".join(lines) if lines else "No transcript turns available."


def _slim_report(report: dict) -> dict:
    """Return a slimmed version of the report for the prompt (drop huge fields)."""
    slim = {k: v for k, v in report.items() if k not in ("generated_at", "report_id", "project_id")}
    # Truncate transcript-heavy fields that are already summarised
    for field in ("question_insights",):
        if field in slim and isinstance(slim[field], list):
            slim[field] = slim[field][:5]  # first 5 only to save tokens
    return slim


def query_report(
    report_id: str,
    query: str,
    include_transcripts: bool = True,
    project_id: Optional[str] = None,
) -> dict:
    """
    Answer a natural-language question about a report.

    Returns:
        {
            "answer": str,          # formatted markdown answer
            "query": str,           # echoed back
            "report_id": str,
            "used_transcripts": bool
        }
    """
    report = load_report(report_id)
    if not report:
        raise ValueError(f"Report {report_id} not found")

    # Load raw transcripts if requested
    transcripts_text = "Not loaded."
    used_transcripts = False
    if include_transcripts:
        pid = project_id or report.get("project_id")
        if pid:
            try:
                from src.core.research_project import get_project
                proj = get_project(pid)
                if proj:
                    tm = TranscriptManager()
                    transcripts = []
                    for sid in (proj._data.get("sessions") or [])[:20]:  # cap at 20
                        t = tm.load(sid)
                        if t:
                            transcripts.append(t)
                    if transcripts:
                        transcripts_text = _extract_relevant_turns(transcripts, query)
                        used_transcripts = True
            except Exception as e:
                logger.warning(f"Could not load transcripts for agent: {e}")

    slim = _slim_report(report)
    report_json = json.dumps(slim, ensure_ascii=False, indent=1)

    # Trim if too long
    if len(report_json) > 60000:
        report_json = report_json[:60000] + "\n... [truncated]"
    if len(transcripts_text) > 20000:
        transcripts_text = transcripts_text[:20000] + "\n... [truncated]"

    prompt = AGENT_PROMPT.format(
        report_json=report_json,
        transcripts_text=transcripts_text,
        query=query,
    )

    client = (
        genai.Client(api_key=settings.gemini_api_key)
        if settings.gemini_api_key
        else genai.Client(vertexai=True, project=settings.gcp_project_id, location=settings.gcp_location)
    )

    logger.info(f"Research Agent query: '{query[:80]}' on report {report_id}")
    response = client.models.generate_content(
        model=settings.gemini_model_pro,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=AGENT_SYSTEM,
            temperature=0.2,
            max_output_tokens=4096,
        ),
    )

    return {
        "answer": response.text.strip(),
        "query": query,
        "report_id": report_id,
        "used_transcripts": used_transcripts,
    }


# Suggested starter queries for the UI
STARTER_QUERIES = [
    "What are the 3 most urgent things to fix based on this research?",
    "Show me the most powerful quotes about pain points",
    "Which recommendations are quick wins I can act on this week?",
    "Compare how different respondent types felt about the experience",
    "What surprised you most in this data?",
    "Summarise the emotional journey in 3 bullet points",
    "Which pain points could directly impact conversion or retention?",
    "What should I present to my CEO from this report?",
]
