"""
quality_scorer.py — Interview quality and fraud detection.

Scores each session transcript on a 0-100 scale using:
  1. Rule-based signals (fast, no API call)
  2. AI evaluation (Gemini Flash — optional, deeper analysis)

Quality labels:
  high_quality    75-100  ✅  Genuine, engaged respondent
  medium_quality  50-74   🟡  Some concerns but usable
  low_quality     25-49   🟠  Thin or disengaged
  suspected_fraud 0-24    🔴  Likely invalid — exclude from analysis

Usage:
  from src.core.quality_scorer import score_transcript

  result = score_transcript(transcript_data, ai_evaluate=True)
  # {
  #   "score": 82,
  #   "label": "high_quality",
  #   "flags": [],
  #   "details": { "response_count": 8, "avg_words": 24, ... },
  #   "ai_summary": "Respondent was engaged and gave detailed answers.",
  #   "ai_issues": []
  # }
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Labels ──────────────────────────────────────────────────────────────────

QUALITY_LABELS = {
    "high_quality":    {"min": 75, "emoji": "✅", "color": "#22c55e", "text": "High quality"},
    "medium_quality":  {"min": 50, "emoji": "🟡", "color": "#f59e0b", "text": "Medium quality"},
    "low_quality":     {"min": 25, "emoji": "🟠", "color": "#f97316", "text": "Low quality"},
    "suspected_fraud": {"min":  0, "emoji": "🔴", "color": "#ef4444", "text": "Suspected fraud"},
}

AI_EVAL_PROMPT = """You are a qualitative research quality analyst reviewing a voice interview transcript.

Assess this transcript for authenticity, engagement, and data quality.

TRANSCRIPT:
{transcript_text}

Evaluate the following and reply in STRICT JSON (no markdown):
{{
  "overall_quality": "good|acceptable|poor|fraud",
  "engagement_level": "high|medium|low",
  "issues": ["list of specific concerns — e.g. contradicts earlier answer, answers are generic/templated, gibberish responses"],
  "has_contradictions": true_or_false,
  "has_gibberish": true_or_false,
  "summary": "1-2 sentence quality assessment"
}}

Return only valid JSON."""


# ── Main scorer ──────────────────────────────────────────────────────────────

def score_transcript(transcript_data: dict, ai_evaluate: bool = False) -> dict:
    """
    Score a transcript for quality and fraud signals.

    Args:
        transcript_data: Full transcript dict from Firestore/TranscriptManager
        ai_evaluate:     Whether to call Gemini Flash for deeper AI analysis

    Returns:
        Quality result dict with score, label, flags, and details.
    """
    conversation = transcript_data.get("conversation", [])
    respondent_turns = [t for t in conversation if t.get("speaker") == "respondent"]

    # ── Rule-based signals ───────────────────────────────────────────────────
    response_count = len(respondent_turns)
    texts = [t.get("text", "").strip() for t in respondent_turns]
    word_counts = [len(t.split()) for t in texts if t]

    total_words = sum(word_counts)
    avg_words = (total_words / len(word_counts)) if word_counts else 0
    short_count = sum(1 for w in word_counts if w < 5)
    short_ratio = (short_count / len(word_counts)) if word_counts else 0
    unique_texts = len(set(t.lower() for t in texts if t))
    unique_ratio = (unique_texts / len(texts)) if texts else 0

    # Duration
    session_secs = _parse_duration(transcript_data)

    # ── Score calculation ────────────────────────────────────────────────────
    score = 100
    flags = []

    # Not enough responses
    if response_count == 0:
        return _make_result(0, ["No respondent turns recorded"], {"response_count": 0}, None, [])

    if response_count < 3:
        score -= 45
        flags.append(f"Only {response_count} response(s) — session too short")

    elif response_count < 5:
        score -= 20
        flags.append(f"Only {response_count} responses — possibly abandoned early")

    # Very low word count
    if total_words < 30:
        score -= 25
        flags.append(f"Very short total response ({total_words} words)")
    elif total_words < 80:
        score -= 10
        flags.append(f"Short overall responses ({total_words} words)")

    # Average response length
    if avg_words < 3:
        score -= 20
        flags.append(f"Extremely short responses (avg {avg_words:.0f} words)")
    elif avg_words < 7:
        score -= 10
        flags.append(f"Very short average response ({avg_words:.1f} words per turn)")

    # High proportion of single-word / ultra-short answers
    if short_ratio > 0.7:
        score -= 20
        flags.append(f"{short_ratio:.0%} of responses are under 5 words (minimal engagement)")
    elif short_ratio > 0.4:
        score -= 8
        flags.append(f"{short_ratio:.0%} of responses are under 5 words")

    # Copy-paste / straight-lining
    if unique_ratio < 0.4 and response_count >= 4:
        score -= 25
        flags.append("Highly repetitive responses — possible copy-paste or bot behaviour")
    elif unique_ratio < 0.6 and response_count >= 4:
        score -= 10
        flags.append("Some repetition in responses")

    # Suspiciously fast session (< 60s with > 3 turns = speed-through)
    if session_secs and session_secs < 60 and response_count >= 3:
        score -= 15
        flags.append(f"Session completed in {session_secs:.0f}s — unusually fast")

    # ── AI evaluation (optional) ─────────────────────────────────────────────
    ai_summary = None
    ai_issues = []

    if ai_evaluate and texts:
        ai_result = _ai_evaluate(conversation)
        ai_summary = ai_result.get("summary", "")
        ai_issues = ai_result.get("issues", [])
        quality = ai_result.get("overall_quality", "acceptable")
        engagement = ai_result.get("engagement_level", "medium")

        if ai_result.get("has_gibberish"):
            score -= 35
            flags.append("AI detected gibberish or incoherent responses")
        if ai_result.get("has_contradictions"):
            score -= 15
            flags.append("AI detected significant contradictions between answers")
        if quality == "fraud":
            score -= 25
            flags.append("AI flagged this session as fraudulent")
        elif quality == "poor":
            score -= 10
            flags.append("AI assessed overall response quality as poor")
        if engagement == "low" and "low engagement" not in " ".join(flags):
            score -= 5
            flags.append("AI assessed engagement level as low")

        for issue in ai_issues[:3]:  # max 3 issues from AI
            if issue and issue not in flags:
                flags.append(f"AI: {issue}")

    score = max(0, min(100, score))

    details = {
        "response_count": response_count,
        "total_words": total_words,
        "avg_words_per_response": round(avg_words, 1),
        "short_response_ratio": round(short_ratio, 2),
        "unique_response_ratio": round(unique_ratio, 2),
        "session_duration_secs": session_secs,
    }

    return _make_result(score, flags, details, ai_summary, ai_issues)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _score_to_label(score: int) -> str:
    if score >= 75:
        return "high_quality"
    if score >= 50:
        return "medium_quality"
    if score >= 25:
        return "low_quality"
    return "suspected_fraud"


def _make_result(score, flags, details, ai_summary, ai_issues) -> dict:
    label = _score_to_label(score)
    meta = QUALITY_LABELS[label]
    return {
        "score": score,
        "label": label,
        "label_text": meta["text"],
        "emoji": meta["emoji"],
        "color": meta["color"],
        "flags": flags,
        "details": details,
        "ai_summary": ai_summary,
        "ai_issues": ai_issues or [],
    }


def _parse_duration(transcript_data: dict) -> Optional[float]:
    """Return session duration in seconds from timestamps, or None."""
    from datetime import datetime
    started = transcript_data.get("started_at") or transcript_data.get("metadata", {}).get("started_at")
    ended = transcript_data.get("ended_at")
    if not started or not ended:
        # Try to compute from first/last turn timestamps
        conv = transcript_data.get("conversation", [])
        ts_list = [t.get("timestamp") for t in conv if t.get("timestamp")]
        if len(ts_list) >= 2:
            started, ended = ts_list[0], ts_list[-1]
        else:
            return None
    try:
        fmt = "%Y-%m-%dT%H:%M:%S"
        s = datetime.fromisoformat(started.split("+")[0].split("Z")[0])
        e = datetime.fromisoformat(ended.split("+")[0].split("Z")[0])
        return (e - s).total_seconds()
    except Exception:
        return None


def _ai_evaluate(conversation: list) -> dict:
    """Call Gemini Flash to holistically assess quality."""
    import json
    from google import genai
    from google.genai import types
    from config.settings import settings

    # Build readable transcript text
    lines = []
    for turn in conversation:
        speaker = "INTERVIEWER" if turn.get("speaker") == "interviewer" else "RESPONDENT"
        text = turn.get("text", "").strip()
        if text:
            lines.append(f"{speaker}: {text}")
    transcript_text = "\n".join(lines)

    if not transcript_text:
        return {"overall_quality": "poor", "engagement_level": "low", "issues": [],
                "has_contradictions": False, "has_gibberish": False, "summary": "No transcript content."}

    prompt = AI_EVAL_PROMPT.format(transcript_text=transcript_text)

    try:
        client = (
            genai.Client(api_key=settings.gemini_api_key)
            if settings.gemini_api_key
            else genai.Client(vertexai=True, project=settings.gcp_project_id, location=settings.gcp_location)
        )
        response = client.models.generate_content(
            model="gemini-2.0-flash",  # flash — fast and cheap
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=512),
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        logger.warning(f"AI quality evaluation failed: {e}")
        return {"overall_quality": "acceptable", "engagement_level": "medium", "issues": [],
                "has_contradictions": False, "has_gibberish": False, "summary": "AI evaluation unavailable."}


def label_meta(label: str) -> dict:
    """Return display metadata for a quality label."""
    return QUALITY_LABELS.get(label, QUALITY_LABELS["medium_quality"])
