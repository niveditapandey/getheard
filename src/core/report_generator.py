"""
AI Report Generator - analyzes interview transcripts and produces research reports.

Takes N transcripts → sends to Gemini → returns structured insights:
  - Executive summary
  - Key themes with frequency + sentiment
  - Question-by-question breakdown
  - Sentiment overview
  - Notable quotes (verbatim)
  - Recommendations
  - Demographic / language breakdown
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

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


ANALYSIS_PROMPT = """You are a senior qualitative research analyst. Analyze the following interview transcripts and produce a comprehensive research report.

RESEARCH CONTEXT:
- Project: {project_name}
- Research Type: {research_type}
- Objective: {objective}
- Total Interviews: {total_interviews}
- Languages: {languages}
- Interview Questions: {questions}

TRANSCRIPTS:
{transcripts_text}

Produce a detailed analysis in the following JSON format (no markdown, pure JSON):
{{
  "executive_summary": "2-3 paragraph narrative summary of the most important findings",
  "methodology": {{
    "total_respondents": {total_interviews},
    "languages_represented": ["list of languages"],
    "avg_turns_per_interview": 0,
    "completion_rate": "XX%"
  }},
  "sentiment_overview": {{
    "overall": "positive|mixed|negative",
    "positive_pct": 0,
    "neutral_pct": 0,
    "negative_pct": 0,
    "sentiment_narrative": "Brief explanation of overall sentiment"
  }},
  "key_themes": [
    {{
      "theme": "Theme name (e.g. Waiting Times)",
      "frequency": 0,
      "frequency_pct": 0,
      "sentiment": "positive|neutral|negative|mixed",
      "description": "What respondents said about this theme",
      "quotes": ["verbatim quote 1", "verbatim quote 2"],
      "sub_themes": ["sub-theme 1", "sub-theme 2"]
    }}
  ],
  "question_insights": [
    {{
      "question_number": 1,
      "question_text": "The question",
      "summary": "What most respondents said",
      "top_responses": ["common response pattern 1", "common response pattern 2", "common response pattern 3"],
      "sentiment": "positive|neutral|negative|mixed",
      "notable_quote": "The most insightful verbatim response"
    }}
  ],
  "notable_quotes": [
    {{
      "quote": "verbatim quote",
      "language": "en",
      "context": "which question/topic this relates to",
      "sentiment": "positive|negative|neutral"
    }}
  ],
  "pain_points": [
    {{
      "pain_point": "Description of the pain point",
      "frequency": 0,
      "severity": "high|medium|low",
      "example": "verbatim example"
    }}
  ],
  "positive_highlights": [
    {{
      "highlight": "What respondents loved",
      "frequency": 0,
      "example": "verbatim example"
    }}
  ],
  "recommendations": [
    {{
      "priority": "high|medium|low",
      "recommendation": "Specific, actionable recommendation",
      "rationale": "Why this is important (evidence from data)",
      "expected_impact": "What improvement this could drive"
    }}
  ],
  "language_insights": [
    {{
      "language": "en",
      "respondents": 0,
      "distinct_patterns": "Any patterns unique to this language group"
    }}
  ],
  "research_gaps": ["Areas that need further research"],
  "confidence_notes": "Notes on data quality, sample size limitations, etc."
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
    questions: Optional[List[dict]] = None,
) -> dict:
    """
    Analyze transcripts with Gemini and return a structured report dict.
    """
    if not transcripts:
        raise ValueError("No transcripts to analyze")

    languages = list({t.get("language_code", "en") for t in transcripts})
    total = len(transcripts)

    questions_text = "Not specified"
    if questions:
        questions_text = "\n".join(
            f"Q{q.get('number', i+1)}: {q.get('main', '')}"
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
        total_interviews=total,
        languages=", ".join(languages),
        questions=questions_text,
        transcripts_text=transcripts_text,
    )

    logger.info(f"Analyzing {total} transcripts for '{project_name}'")
    response = client.models.generate_content(
        model=settings.gemini_model_pro,  # pro — deep analysis report
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="You are a senior qualitative research analyst. Always return pure JSON, no markdown, no explanation outside the JSON.",
            temperature=0.3,
            max_output_tokens=8192,
        ),
    )

    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    analysis = json.loads(raw)

    # Wrap with metadata
    report = {
        "report_id": str(uuid.uuid4())[:8],
        "project_name": project_name,
        "research_type": research_type,
        "objective": objective,
        "generated_at": datetime.now().isoformat(),
        "total_transcripts": total,
        "languages": languages,
        **analysis,
    }

    # Persist
    report_path = REPORTS_DIR / f"{report['report_id']}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Report {report['report_id']} saved")

    return report


def load_report(report_id: str) -> Optional[dict]:
    path = REPORTS_DIR / f"{report_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_reports() -> List[dict]:
    results = []
    for f in sorted(REPORTS_DIR.glob("*.json"), reverse=True):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "report_id": d["report_id"],
                "project_name": d.get("project_name", "Unnamed"),
                "generated_at": d.get("generated_at", ""),
                "total_transcripts": d.get("total_transcripts", 0),
            })
        except Exception:
            pass
    return results
