"""
mission_control.py — Cross-study NL query engine.

Unlike the per-report Research Agent, Mission Control queries across ALL projects,
reports, and transcripts simultaneously. Useful for:

  "Which of our studies had the most price sensitivity mentions?"
  "Show all quotes about trust across every study"
  "What recurring themes appear across our healthcare and fintech projects?"
  "Which project should we prioritise for follow-up research?"
  "Summarise what we've learned about millennials across all our work"

Architecture:
  1. Load all reports from Firestore (summaries — lean JSON)
  2. Load a cross-study sample of transcripts (capped for token budget)
  3. Build a rich context block grouped by project
  4. Send to Gemini Pro with a cross-study analyst prompt
"""

import json
import logging
from typing import Optional

from google import genai
from google.genai import types

from config.settings import settings
from src.storage.firestore_db import db, REPORTS, TRANSCRIPTS, PROJECTS

logger = logging.getLogger(__name__)

# ── Prompts ───────────────────────────────────────────────────────────────────

MISSION_SYSTEM = """You are a senior research strategist with access to ALL research studies
conducted on GetHeard. Your job is to surface patterns, comparisons, and strategic insights
that span multiple projects — the kind of synthesis a strategy director would pay for.

Rules:
1. Always cite which project(s) your evidence comes from (use project name).
2. Highlight cross-study patterns prominently — that is your unique value.
3. Quote directly from transcripts when making claims about respondents.
4. Be specific and actionable. Avoid vague generalisations.
5. Use **bold** for key findings, bullet points for lists.
6. End with a "Cross-Study Takeaway" section with 2-3 strategic insights."""


MISSION_PROMPT = """You have access to all research conducted on this platform.

=== ALL PROJECTS & REPORTS ===
{projects_block}

=== CROSS-STUDY TRANSCRIPT SAMPLE ===
{transcripts_block}

=== ANALYST QUESTION ===
{query}

Answer drawing on ALL the above data. Cite project names and quote respondents as evidence."""


OVERVIEW_PROMPT = """You are a research intelligence system. Based on the following research data,
generate a strategic overview.

{projects_block}

Return ONLY valid JSON (no markdown):
{{
  "headline": "1-sentence summary of the most important cross-study finding",
  "top_themes": ["theme1", "theme2", "theme3"],
  "projects_at_a_glance": [
    {{"name": "Project Name", "key_finding": "one line", "sentiment": "positive|neutral|negative"}}
  ],
  "recommended_follow_ups": ["follow-up 1", "follow-up 2"]
}}"""


MISSION_STARTER_QUERIES = [
    "What recurring pain points appear across all our studies?",
    "Which project has the strongest signal for immediate action?",
    "Show me all quotes about price or cost across every study",
    "Compare sentiment across our different projects",
    "What do we know about trust from all our research?",
    "Which audience segments appear across multiple studies?",
    "What should I present to leadership as our top 3 learnings?",
    "Where are the biggest gaps in our research coverage?",
]


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_all_reports(max_reports: int = 20) -> list:
    """Load all reports from Firestore, returning lean summaries."""
    try:
        docs = db.collection(REPORTS).order_by("generated_at", direction="DESCENDING").limit(max_reports).stream()
        reports = []
        for doc in docs:
            d = doc.to_dict()
            if not d:
                continue
            # Keep only the analytically valuable fields — drop verbatim text to save tokens
            slim = {
                "report_id":    d.get("report_id"),
                "project_name": d.get("project_name"),
                "project_id":   d.get("project_id"),
                "research_type": d.get("research_type"),
                "generated_at": d.get("generated_at"),
                "total_transcripts": d.get("total_transcripts"),
                "key_themes":   d.get("key_themes", []),
                "pain_points":  d.get("pain_points", []),
                "positive_highlights": d.get("positive_highlights", []),
                "recommendations": d.get("recommendations", [])[:5],
                "personas":     d.get("personas", []),
                "research_gaps": d.get("research_gaps", []),
                "executive_summary": d.get("executive_summary", ""),
                "key_stat":     d.get("key_stat"),
            }
            reports.append(slim)
        return reports
    except Exception as e:
        logger.warning(f"Failed to load reports from Firestore: {e}")
        return []


def _load_cross_study_transcripts(project_ids: list, max_per_project: int = 5, max_turns: int = 80) -> list:
    """Load a cross-study transcript sample, capped for the token budget."""
    from src.storage.transcript import TranscriptManager
    from src.core.research_project import get_project

    tm = TranscriptManager()
    all_turns = []  # [{project_name, lang, text}]

    for pid in project_ids:
        if not pid:
            continue
        try:
            proj = get_project(pid)
            if not proj:
                continue
            session_ids = (proj._data.get("sessions") or [])[:max_per_project]
            for sid in session_ids:
                t = tm.load(sid)
                if not t:
                    continue
                lang = t.get("language_code", "en")
                for turn in t.get("conversation", []):
                    if turn.get("speaker") == "respondent" and turn.get("text", "").strip():
                        all_turns.append({
                            "project": proj.name,
                            "lang": lang,
                            "text": turn["text"].strip(),
                        })
        except Exception as e:
            logger.warning(f"Failed to load transcripts for project {pid}: {e}")

    # Sample if too many
    if len(all_turns) > max_turns:
        step = max(1, len(all_turns) // max_turns)
        all_turns = all_turns[::step][:max_turns]

    return all_turns


def _build_projects_block(reports: list) -> str:
    """Format all reports into a readable context block."""
    if not reports:
        return "No reports found."
    blocks = []
    for r in reports:
        themes = "; ".join(
            (t.get("title") or t) if isinstance(t, dict) else str(t)
            for t in (r.get("key_themes") or [])[:4]
        )
        pains = "; ".join(
            (p.get("pain") or p) if isinstance(p, dict) else str(p)
            for p in (r.get("pain_points") or [])[:3]
        )
        recs = "; ".join(
            (rec.get("action") or rec) if isinstance(rec, dict) else str(rec)
            for rec in (r.get("recommendations") or [])[:3]
        )
        blocks.append(
            f"PROJECT: {r.get('project_name', 'Unknown')} | Type: {r.get('research_type', '')}\n"
            f"  Summary: {r.get('executive_summary', '')[:300]}\n"
            f"  Key themes: {themes}\n"
            f"  Pain points: {pains}\n"
            f"  Recommendations: {recs}\n"
            f"  Interviews: {r.get('total_transcripts', '?')}"
        )
    return "\n\n".join(blocks)


def _build_transcripts_block(turns: list) -> str:
    if not turns:
        return "No transcript data available."
    lines = [f"[{t['project']} | {t['lang']}] {t['text']}" for t in turns]
    return "\n".join(lines)


# ── Main query ────────────────────────────────────────────────────────────────

def query_mission_control(query: str) -> dict:
    """
    Answer a cross-study NL query.

    Returns:
        {
            "answer": str,
            "query": str,
            "projects_consulted": int,
            "transcripts_sampled": int,
        }
    """
    reports = _load_all_reports()
    project_ids = list({r.get("project_id") for r in reports if r.get("project_id")})

    turns = _load_cross_study_transcripts(project_ids)
    projects_block = _build_projects_block(reports)
    transcripts_block = _build_transcripts_block(turns)

    # Trim if needed
    if len(projects_block) > 50000:
        projects_block = projects_block[:50000] + "\n...[truncated]"
    if len(transcripts_block) > 20000:
        transcripts_block = transcripts_block[:20000] + "\n...[truncated]"

    prompt = MISSION_PROMPT.format(
        projects_block=projects_block,
        transcripts_block=transcripts_block,
        query=query,
    )

    client = (
        genai.Client(api_key=settings.gemini_api_key)
        if settings.gemini_api_key
        else genai.Client(vertexai=True, project=settings.gcp_project_id, location=settings.gcp_location)
    )

    logger.info(f"Mission Control query: '{query[:80]}' | {len(reports)} reports, {len(turns)} transcript turns")

    response = client.models.generate_content(
        model=settings.gemini_model_pro,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=MISSION_SYSTEM,
            temperature=0.2,
            max_output_tokens=4096,
        ),
    )

    return {
        "answer": response.text.strip(),
        "query": query,
        "projects_consulted": len(reports),
        "transcripts_sampled": len(turns),
    }


def get_mission_overview() -> dict:
    """
    Generate a strategic overview across all studies.
    Returns structured JSON for the dashboard header.
    """
    reports = _load_all_reports(max_reports=10)
    if not reports:
        return {
            "headline": "No research data yet. Run some studies to unlock Mission Control insights.",
            "top_themes": [],
            "projects_at_a_glance": [],
            "recommended_follow_ups": [],
            "total_projects": 0,
            "total_reports": 0,
        }

    projects_block = _build_projects_block(reports)
    prompt = OVERVIEW_PROMPT.format(projects_block=projects_block)

    client = (
        genai.Client(api_key=settings.gemini_api_key)
        if settings.gemini_api_key
        else genai.Client(vertexai=True, project=settings.gcp_project_id, location=settings.gcp_location)
    )

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=1024),
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
    except Exception as e:
        logger.warning(f"Mission overview generation failed: {e}")
        result = {
            "headline": "Research intelligence ready.",
            "top_themes": [],
            "projects_at_a_glance": [],
            "recommended_follow_ups": [],
        }

    result["total_projects"] = len({r.get("project_id") for r in reports if r.get("project_id")})
    result["total_reports"] = len(reports)
    return result
