"""
AI Report Generator - analyzes interview transcripts and produces consultant-grade research reports.

Takes N transcripts → sends to Gemini Pro → returns structured insights:
  - Executive summary with business implications
  - Respondent personas (derived archetypes)
  - Emotional journey arc across questions
  - Key themes with frequency, sentiment, evidence
  - Pain points + positive highlights
  - Opportunity matrix (impact vs effort)
  - Notable verbatim quotes
  - Actionable recommendations
  - Research gaps & confidence notes
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from google import genai
from google.genai import types

from config.settings import settings
from src.storage.firestore_db import get_db

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


ANALYSIS_PROMPT = """You are a principal qualitative research analyst at a top-tier insights consultancy. \
Your reports are used by C-suite executives to make million-dollar product decisions. \
Analyze the following interview transcripts and produce an authoritative, evidence-rich research report.

RESEARCH CONTEXT:
- Project: {project_name}
- Research Type: {research_type}
- Objective: {objective}
- Target Audience: {audience}
- Total Interviews Analyzed: {total_interviews}
- Languages: {languages}
- Interview Questions:
{questions}

TRANSCRIPTS:
{transcripts_text}

INSTRUCTIONS:
1. Ground every insight in specific evidence from the transcripts. Never speculate beyond the data.
2. Use verbatim quotes generously — they are the most credible form of evidence.
3. Identify patterns across respondents, not just individual responses.
4. Frame pain points in terms of business outcomes (conversion, retention, NPS, revenue).
5. Make recommendations specific, actionable, and tied to evidence.
6. Derive 2-4 respondent personas from behavioral patterns in the data.
7. Map the emotional arc respondents experience across the interview questions.
8. Score each recommendation by business impact (1-10) and implementation effort (1-10).

Produce your analysis as pure JSON (no markdown, no text outside the JSON):

{{
  "executive_summary": "3-4 paragraph narrative. Para 1: Context and what was studied. Para 2: The single most important finding and its business implication. Para 3: Key patterns across respondents. Para 4: Urgent call to action.",

  "key_stat": "The single most striking quantitative finding (e.g., '7 of 8 respondents mentioned X' or '90% of participants experienced Y')",

  "methodology": {{
    "total_respondents": {total_interviews},
    "languages_represented": ["list"],
    "avg_turns_per_interview": 0,
    "completion_rate": "XX%",
    "data_richness": "high|medium|low",
    "notes": "Any methodological considerations"
  }},

  "sentiment_overview": {{
    "overall": "positive|mixed|negative",
    "positive_pct": 0,
    "neutral_pct": 0,
    "negative_pct": 0,
    "sentiment_narrative": "2-3 sentences explaining the emotional tone and what drives it"
  }},

  "personas": [
    {{
      "name": "A vivid, memorable archetype name (e.g., 'The Cautious Converter')",
      "percentage": 0,
      "description": "2-3 sentence description of this respondent type",
      "characteristics": ["trait 1", "trait 2", "trait 3"],
      "primary_motivation": "What they are trying to achieve",
      "primary_frustration": "Their biggest pain point",
      "key_quote": "The most representative verbatim quote from this persona type",
      "what_they_need": "What would make their experience dramatically better"
    }}
  ],

  "emotional_journey": [
    {{
      "stage": "Stage name (e.g., 'Initial Context', 'Core Experience', 'Pain Discovery', 'Resolution')",
      "question_numbers": [1, 2],
      "dominant_emotion": "e.g., curious, frustrated, resigned, hopeful, satisfied",
      "valence_score": 5,
      "description": "What respondents were feeling at this stage and why",
      "turning_point": "Was there a shift in emotion here? If so, what caused it?"
    }}
  ],

  "key_themes": [
    {{
      "theme": "Theme name (concise, specific)",
      "frequency": 0,
      "frequency_pct": 0,
      "sentiment": "positive|neutral|negative|mixed",
      "description": "What respondents said about this — specific patterns, not generalizations",
      "business_implication": "Why this matters for the business",
      "quotes": ["verbatim quote 1", "verbatim quote 2"],
      "sub_themes": ["sub-theme 1", "sub-theme 2"]
    }}
  ],

  "question_insights": [
    {{
      "question_number": 1,
      "question_text": "The question",
      "summary": "What the majority of respondents said — specific and evidence-backed",
      "top_responses": ["pattern 1 with example", "pattern 2 with example", "pattern 3 with example"],
      "sentiment": "positive|neutral|negative|mixed",
      "notable_quote": "The single most insightful or representative verbatim quote",
      "unexpected_finding": "Anything surprising or counter-intuitive from responses to this question"
    }}
  ],

  "notable_quotes": [
    {{
      "quote": "verbatim quote — preserve exact words",
      "language": "en",
      "context": "Which question/topic this relates to",
      "sentiment": "positive|negative|neutral",
      "why_notable": "Why this quote is particularly powerful or revealing"
    }}
  ],

  "pain_points": [
    {{
      "pain_point": "Specific, concrete description",
      "frequency": 0,
      "severity": "high|medium|low",
      "business_impact": "What metric this affects — e.g., 'drives 30% drop-off at KYC step'",
      "example": "verbatim example",
      "root_cause": "Underlying cause of this pain"
    }}
  ],

  "positive_highlights": [
    {{
      "highlight": "What respondents valued or loved",
      "frequency": 0,
      "business_value": "Why this matters — what to protect or amplify",
      "example": "verbatim example"
    }}
  ],

  "opportunity_matrix": [
    {{
      "recommendation": "Specific, actionable recommendation",
      "impact_score": 0,
      "effort_score": 0,
      "category": "quick_win|strategic|backburner|fill_in",
      "business_metric": "The metric this moves — e.g., conversion_rate, retention, nps, revenue, trust",
      "rationale": "Evidence from the data",
      "expected_impact": "Specific expected outcome"
    }}
  ],

  "recommendations": [
    {{
      "priority": "high|medium|low",
      "recommendation": "Specific, actionable recommendation",
      "rationale": "Evidence from the data that supports this",
      "expected_impact": "What improvement this could drive, as specifically as possible",
      "who_owns_it": "Product|Design|Engineering|Marketing|Operations|Leadership"
    }}
  ],

  "language_insights": [
    {{
      "language": "en",
      "respondents": 0,
      "distinct_patterns": "Any patterns unique to this language/cultural group vs others"
    }}
  ],

  "research_gaps": ["Specific areas the data couldn't answer that warrant follow-up research"],
  "confidence_notes": "Honest assessment of data quality, sample representativeness, and where conclusions are stronger vs weaker"
}}"""


def _format_transcripts(transcripts: List[dict]) -> str:
    """Format transcripts into readable text for the LLM."""
    parts = []
    for i, t in enumerate(transcripts, 1):
        lang = t.get("language_code", "en")
        conv = t.get("conversation", [])
        turns = "\n".join(
            f"  {'ALEX' if m['speaker'] == 'interviewer' else 'RESPONDENT'}: {m.get('text', m.get('content', ''))}"
            for m in conv
        )
        parts.append(f"--- Interview {i} (Language: {lang}) ---\n{turns}")
    return "\n\n".join(parts)


def generate_report(
    transcripts: List[dict],
    project_name: str = "Unnamed Research",
    research_type: str = "cx",
    objective: str = "Understand customer experience",
    audience: str = "General consumers",
    questions: Optional[List[dict]] = None,
    project_id: Optional[str] = None,
) -> dict:
    """
    Analyze transcripts with Gemini Pro and return a structured report dict.
    Saves to both local JSON (cache) and Firestore (production persistence).
    """
    if not transcripts:
        raise ValueError("No transcripts to analyze")

    languages = list({t.get("language_code", "en") for t in transcripts})
    total = len(transcripts)

    questions_text = "Not specified"
    if questions:
        questions_text = "\n".join(
            f"  Q{q.get('number', i+1)}: {q.get('main', '')}"
            + (f"\n  (Probe: {q.get('probe', '')})" if q.get("probe") else "")
            for i, q in enumerate(questions)
        )

    transcripts_text = _format_transcripts(transcripts)

    client = (
        genai.Client(api_key=settings.gemini_api_key)
        if settings.gemini_api_key
        else genai.Client(vertexai=True, project=settings.gcp_project_id, location=settings.gcp_location)
    )

    prompt = ANALYSIS_PROMPT.format(
        project_name=project_name,
        research_type=research_type,
        objective=objective,
        audience=audience,
        total_interviews=total,
        languages=", ".join(languages),
        questions=questions_text,
        transcripts_text=transcripts_text,
    )

    logger.info(f"Analyzing {total} transcripts for '{project_name}' with Gemini Pro")
    response = client.models.generate_content(
        model=settings.gemini_model_pro,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are a principal qualitative research analyst. "
                "Always return pure JSON with no markdown, no code fences, no text outside the JSON object. "
                "Be specific and evidence-backed in all insights. Use verbatim quotes."
            ),
            temperature=0.2,
            max_output_tokens=16384,
        ),
    )

    raw = response.text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    analysis = json.loads(raw)

    report_id = str(uuid.uuid4())[:8]
    report = {
        "report_id": report_id,
        "project_id": project_id,
        "project_name": project_name,
        "research_type": research_type,
        "objective": objective,
        "audience": audience,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_transcripts": total,
        "languages": languages,
        **analysis,
    }

    # Save to local JSON (cache / dev fallback)
    report_path = REPORTS_DIR / f"{report_id}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Save to Firestore (production persistence, survives Cloud Run restarts)
    try:
        db = get_db()
        db.collection("reports").document(report_id).set(report)
        logger.info(f"Report {report_id} saved to Firestore")
    except Exception as e:
        logger.warning(f"Firestore save failed (falling back to local JSON): {e}")

    logger.info(f"Report {report_id} generated for '{project_name}'")
    return report


def load_report(report_id: str) -> Optional[dict]:
    """Load report from Firestore first, fall back to local JSON."""
    try:
        db = get_db()
        doc = db.collection("reports").document(report_id).get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        logger.warning(f"Firestore load failed, trying local: {e}")

    path = REPORTS_DIR / f"{report_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def list_reports() -> List[dict]:
    """List all reports from Firestore first, fall back to local JSON."""
    try:
        db = get_db()
        docs = db.collection("reports").order_by("generated_at", direction="DESCENDING").limit(50).stream()
        results = []
        for doc in docs:
            d = doc.to_dict()
            results.append({
                "report_id": d.get("report_id", doc.id),
                "project_id": d.get("project_id"),
                "project_name": d.get("project_name", "Unnamed"),
                "generated_at": d.get("generated_at", ""),
                "total_transcripts": d.get("total_transcripts", 0),
                "key_stat": d.get("key_stat", ""),
            })
        if results:
            return results
    except Exception as e:
        logger.warning(f"Firestore list failed, trying local: {e}")

    # Fallback to local JSON
    results = []
    for f in sorted(REPORTS_DIR.glob("*.json"), reverse=True):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "report_id": d["report_id"],
                "project_id": d.get("project_id"),
                "project_name": d.get("project_name", "Unnamed"),
                "generated_at": d.get("generated_at", ""),
                "total_transcripts": d.get("total_transcripts", 0),
                "key_stat": d.get("key_stat", ""),
            })
        except Exception:
            pass
    return results
