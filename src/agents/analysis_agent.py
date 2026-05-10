"""
AnalysisAgent — 4-pass transcript analysis engine.

Replaces the one-shot generate_report() call with a genuine multi-step
reasoning process that mimics how a senior analyst would work:

  Pass 1 — EXTRACT:     Analyse each transcript individually
  Pass 2 — SYNTHESIZE:  Find patterns across all transcripts
  Pass 3 — WRITE:       Draft each report section
  Pass 4 — CRITIQUE:    Review own report, find gaps, patch them

Each pass stores structured data via tools. The final report is an enriched
dict that is backward-compatible with the existing report.html template.

Usage:
    agent = AnalysisAgent(transcripts, project_name, research_type, objective)
    report = await agent.analyze()   # Dict — save to reports/ as JSON
"""

import logging
from typing import Dict, List, Optional

from config.settings import settings
from .base_agent import BaseAgent, ToolSpec

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """You are a principal qualitative research analyst with expertise in Asian consumer markets.

Your task: produce a rigorous, evidence-based research report from interview transcripts.

━━ YOUR 4-PASS WORKFLOW ━━

Pass 1 — EXTRACT (call extract_themes once per transcript)
  • Read each transcript carefully
  • Extract: dominant themes, sentiment, key verbatim quotes, pain points, highlights
  • Note: what question prompted this, what was left unanswered

Pass 2 — SYNTHESIZE (call synthesize_patterns once, after all transcripts)
  • Find themes that appear across multiple transcripts
  • Note the frequency (how many respondents mentioned each theme)
  • Identify contradictions between respondents — don't paper over them
  • Calculate overall sentiment from per-transcript sentiments

Pass 3 — WRITE (call write_sections once)
  • Executive summary: 3–5 sentences, most important finding first
  • Key findings: bullet points grounded in evidence
  • Pain points vs positive highlights (balanced)
  • Actionable recommendations with priority (high/medium/low)
  • Research gaps: what this study could not answer

Pass 4 — CRITIQUE (call self_critique, then finalize)
  • Ask yourself: "What would a senior client push back on?"
  • Identify claims without evidence, missing perspectives, weak recommendations
  • Apply any patches to improve the report
  • Then call finalize_report

━━ QUALITY STANDARDS ━━
  ✓ Every claim needs supporting evidence from transcripts
  ✓ Distinguish strong patterns (3+ respondents) from individual observations
  ✓ Contradictions between respondents must be named, not ignored
  ✓ Recommendations must be specific and actionable, not generic
  ✓ Note when sample size limits confidence in a finding
  ✗ Never invent quotes or extrapolate beyond the data"""


class AnalysisAgent(BaseAgent):
    """
    Multi-pass research report generator.

    The agent runs 4 structured passes over the transcript data using
    tool calls, storing intermediate results at each stage.
    """

    def __init__(
        self,
        transcripts: List[Dict],
        project_name: str,
        research_type: str,
        objective: str,
        questions: Optional[List[Dict]] = None,
    ):
        super().__init__()
        self.name = "AnalysisAgent"
        self.model = settings.gemini_model_pro  # pro — 4-pass deep reasoning, quality over speed
        self.system_prompt = ANALYSIS_SYSTEM_PROMPT
        self.transcripts = transcripts
        self.project_name = project_name
        self.research_type = research_type
        self.objective = objective
        self.questions = questions or []

        # Storage for each pass
        self._per_transcript: List[Dict] = []
        self._patterns: Optional[Dict] = None
        self._sections: Optional[Dict] = None
        self._critique: Optional[Dict] = None
        self.final_report: Optional[Dict] = None

        self._register_tools()

    # ── Tool registration ────────────────────────────────────────────────────

    def _register_tools(self):
        # Pass 1
        self.register_tool(ToolSpec(
            name="extract_themes",
            description=(
                "Store the analysis for ONE transcript. "
                "Call this once per transcript before synthesizing."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "transcript_index": {"type": "integer", "description": "0-based index of this transcript"},
                    "language":         {"type": "string"},
                    "sentiment":        {"type": "string", "enum": ["positive", "neutral", "negative", "mixed"]},
                    "dominant_themes":  {"type": "array", "items": {"type": "string"}},
                    "key_quotes":       {
                        "type": "array",
                        "description": "Verbatim quotes from the respondent (exact words)",
                        "items": {"type": "string"},
                    },
                    "pain_points":      {"type": "array", "items": {"type": "string"}},
                    "positive_moments": {"type": "array", "items": {"type": "string"}},
                    "unanswered":       {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Questions the respondent deflected or couldn't answer",
                    },
                },
                "required": ["transcript_index", "language", "sentiment", "dominant_themes", "key_quotes"],
            },
            handler=self._extract_themes_handler,
        ))

        # Pass 2
        self.register_tool(ToolSpec(
            name="synthesize_patterns",
            description=(
                "Synthesize findings across ALL transcripts. "
                "Call this after extract_themes has been called for every transcript."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "key_themes": {
                        "type": "array",
                        "description": "Themes that appear across multiple transcripts",
                        "items": {
                            "type": "object",
                            "properties": {
                                "theme":          {"type": "string"},
                                "frequency":      {"type": "integer", "description": "Number of respondents who mentioned this"},
                                "sentiment":      {"type": "string", "enum": ["positive", "neutral", "negative", "mixed"]},
                                "example_quotes": {"type": "array", "items": {"type": "string"}},
                                "strength":       {"type": "string", "enum": ["strong", "moderate", "weak"], "description": "Evidence strength"},
                            },
                            "required": ["theme", "frequency", "sentiment", "example_quotes", "strength"],
                        },
                    },
                    "overall_sentiment": {"type": "string", "enum": ["positive", "neutral", "negative", "mixed"]},
                    "sentiment_breakdown": {
                        "type": "object",
                        "properties": {
                            "positive": {"type": "integer"},
                            "neutral":  {"type": "integer"},
                            "negative": {"type": "integer"},
                            "mixed":    {"type": "integer"},
                        },
                    },
                    "contradictions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Where respondents significantly disagreed with each other",
                    },
                    "language_insights": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Observations about how findings differed by language/market",
                    },
                },
                "required": ["key_themes", "overall_sentiment", "sentiment_breakdown"],
            },
            handler=self._synthesize_patterns_handler,
        ))

        # Pass 3
        self.register_tool(ToolSpec(
            name="write_sections",
            description="Write all report sections. Call this after synthesize_patterns.",
            parameters={
                "type": "object",
                "properties": {
                    "executive_summary": {"type": "string", "description": "3–5 sentence summary, most important finding first"},
                    "methodology":       {"type": "string", "description": "Brief description of how the research was conducted"},
                    "key_findings":      {"type": "string", "description": "Main findings as bullet-point narrative"},
                    "pain_points":       {"type": "array", "items": {"type": "string"}},
                    "positive_highlights": {"type": "array", "items": {"type": "string"}},
                    "recommendations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "priority":  {"type": "string", "enum": ["high", "medium", "low"]},
                                "action":    {"type": "string"},
                                "rationale": {"type": "string", "description": "Evidence basis for this recommendation"},
                            },
                            "required": ["priority", "action", "rationale"],
                        },
                    },
                    "notable_quotes":  {"type": "array", "items": {"type": "string"}},
                    "research_gaps":   {"type": "array", "items": {"type": "string"}},
                    "question_insights": {
                        "type": "array",
                        "description": "Per-question insights (optional)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question":    {"type": "string"},
                                "insight":     {"type": "string"},
                                "top_quote":   {"type": "string"},
                            },
                        },
                    },
                },
                "required": [
                    "executive_summary", "methodology", "key_findings",
                    "pain_points", "positive_highlights", "recommendations",
                    "notable_quotes", "research_gaps",
                ],
            },
            handler=self._write_sections_handler,
        ))

        # Pass 4a — critique
        self.register_tool(ToolSpec(
            name="self_critique",
            description=(
                "Review your own report critically. "
                "Identify weak claims, missing evidence, or gaps. "
                "Apply patches to fix them. Call before finalize_report."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "gaps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Missing analyses or underdeveloped sections",
                    },
                    "confidence_notes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Caveats about reliability (small sample, single language, etc.)",
                    },
                    "section_patches": {
                        "type": "array",
                        "description": "Text to append to specific sections to improve them",
                        "items": {
                            "type": "object",
                            "properties": {
                                "section":  {"type": "string", "description": "Section name (e.g. 'executive_summary', 'key_findings')"},
                                "addition": {"type": "string"},
                            },
                            "required": ["section", "addition"],
                        },
                    },
                },
                "required": ["gaps", "confidence_notes"],
            },
            handler=self._self_critique_handler,
        ))

        # Pass 4b — finalize
        self.register_tool(ToolSpec(
            name="finalize_report",
            description="Mark the report as complete. Call after self_critique.",
            parameters={
                "type": "object",
                "properties": {
                    "report_quality": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "Overall confidence in the report's findings",
                    },
                    "tldr": {
                        "type": "string",
                        "description": "One-paragraph plain-English summary for the client",
                    },
                },
                "required": ["report_quality", "tldr"],
            },
            handler=self._finalize_report_handler,
        ))

    # ── Tool handlers ────────────────────────────────────────────────────────

    async def _extract_themes_handler(self, **kwargs) -> Dict:
        idx = kwargs.get("transcript_index", len(self._per_transcript))
        self._per_transcript.append(kwargs)
        logger.info(f"[AnalysisAgent] Extracted themes for transcript {idx}")
        return {"status": "stored", "transcript_index": idx}

    async def _synthesize_patterns_handler(self, **kwargs) -> Dict:
        self._patterns = kwargs
        theme_count = len(kwargs.get("key_themes", []))
        logger.info(f"[AnalysisAgent] Synthesized {theme_count} cross-transcript themes")
        return {"status": "stored", "theme_count": theme_count}

    async def _write_sections_handler(self, **kwargs) -> Dict:
        self._sections = kwargs
        logger.info("[AnalysisAgent] Report sections written")
        return {"status": "stored"}

    async def _self_critique_handler(
        self,
        gaps: List[str],
        confidence_notes: List[str],
        section_patches: Optional[List[Dict]] = None,
    ) -> Dict:
        self._critique = {
            "gaps": gaps,
            "confidence_notes": confidence_notes,
            "section_patches": section_patches or [],
        }
        # Apply patches directly to sections
        if self._sections and section_patches:
            for patch in section_patches:
                section = patch.get("section", "")
                addition = patch.get("addition", "")
                if section in self._sections and addition:
                    existing = self._sections[section]
                    if isinstance(existing, str):
                        self._sections[section] = existing + "\n\n" + addition
                    elif isinstance(existing, list):
                        self._sections[section].append(addition)
        logger.info(
            f"[AnalysisAgent] Self-critique: {len(gaps)} gaps, "
            f"{len(section_patches or [])} patches applied"
        )
        return {"status": "critique_applied", "patches_applied": len(section_patches or [])}

    async def _finalize_report_handler(self, report_quality: str, tldr: str) -> Dict:
        s = self._sections or {}
        p = self._patterns or {}
        c = self._critique or {}

        self.final_report = {
            # ── Metadata ──
            "project_name":        self.project_name,
            "research_type":       self.research_type,
            "objective":           self.objective,
            "total_transcripts":   len(self.transcripts),
            "report_quality":      report_quality,
            "tldr":                tldr,

            # ── Backward-compatible fields for report.html ──
            "executive_summary":   s.get("executive_summary", ""),
            "methodology":         s.get("methodology", ""),
            "key_themes":          p.get("key_themes", []),
            "overall_sentiment":   p.get("overall_sentiment", "neutral"),
            "sentiment_overview":  p.get("sentiment_breakdown", {}),
            "sentiment_breakdown": p.get("sentiment_breakdown", {}),
            "pain_points":         s.get("pain_points", []),
            "positive_highlights": s.get("positive_highlights", []),
            "recommendations":     s.get("recommendations", []),
            "notable_quotes":      s.get("notable_quotes", []),
            "research_gaps":       s.get("research_gaps", []),
            "question_insights":   s.get("question_insights", []),
            "confidence_notes":    c.get("confidence_notes", []),
            "language_insights":   p.get("language_insights", []),
            "contradictions":      p.get("contradictions", []),

            # ── Agent-specific enrichment ──
            "agent_passes": {
                "per_transcript_analysis": self._per_transcript,
                "pattern_synthesis":       self._patterns,
                "written_sections":        self._sections,
                "self_critique":           self._critique,
            },
        }
        logger.info(
            f"[AnalysisAgent] Report finalized (quality={report_quality}, "
            f"themes={len(p.get('key_themes', []))})"
        )
        return {"status": "finalized", "report_quality": report_quality}

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _format_transcripts(self) -> str:
        parts = []
        for i, t in enumerate(self.transcripts):
            lang = t.get("language_code", "unknown")
            conv = t.get("conversation", [])
            turns = "\n".join(
                f"{'Interviewer' if m.get('speaker') == 'interviewer' else 'Respondent'}: "
                f"{m.get('text') or m.get('content', '')}"
                for m in conv
            )
            parts.append(f"=== Transcript {i + 1} | Language: {lang} ===\n{turns}")
        return "\n\n".join(parts)

    # ── Public interface ─────────────────────────────────────────────────────

    async def analyze(self) -> Dict:
        """
        Run all 4 passes explicitly — one Gemini call per pass.
        This avoids relying on autonomous tool chaining which hits iteration limits.
        """
        n = len(self.transcripts)
        context_header = (
            f"Research Study: {self.project_name}\n"
            f"Type: {self.research_type}\n"
            f"Objective: {self.objective}\n"
            f"Total Interviews: {n}\n\n"
        )

        # ── Pass 1: extract_themes per transcript ────────────────────────────
        for i, t in enumerate(self.transcripts):
            lang = t.get("language_code", "unknown")
            conv = t.get("conversation", [])
            turns = "\n".join(
                f"{'Interviewer' if m.get('speaker') == 'interviewer' else 'Respondent'}: "
                f"{m.get('text') or m.get('content', '')}"
                for m in conv
            )
            prompt = (
                context_header +
                f"=== Transcript {i+1}/{n} | Language: {lang} ===\n{turns}\n\n"
                f"Call extract_themes() now for this transcript (index={i}). "
                "Extract themes, sentiment, key quotes, pain points and positive moments."
            )
            self.reset()
            await self.run(prompt)
            logger.info(f"[AnalysisAgent] Pass 1 complete: transcript {i+1}/{n}")

        # ── Pass 2: synthesize_patterns ──────────────────────────────────────
        extracts_summary = "\n".join(
            f"Transcript {i+1} ({e.get('language','?')}): "
            f"sentiment={e.get('sentiment')}, "
            f"themes={e.get('dominant_themes',[])} "
            f"pain_points={e.get('pain_points',[])}"
            for i, e in enumerate(self._per_transcript)
        )
        self.reset()
        await self.run(
            context_header +
            f"Per-transcript extracts:\n{extracts_summary}\n\n"
            "Call synthesize_patterns() to find cross-transcript themes, "
            "overall sentiment, contradictions, and language-market differences."
        )
        logger.info("[AnalysisAgent] Pass 2 complete: patterns synthesized")

        # ── Pass 3: write_sections ───────────────────────────────────────────
        patterns_summary = (
            f"Key themes: {[t.get('theme') for t in (self._patterns or {}).get('key_themes',[])]}\n"
            f"Sentiment: {(self._patterns or {}).get('overall_sentiment')}\n"
            f"Contradictions: {(self._patterns or {}).get('contradictions',[])}"
        )
        all_quotes = [
            q for e in self._per_transcript for q in e.get("key_quotes", [])
        ]
        self.reset()
        await self.run(
            context_header +
            f"Patterns:\n{patterns_summary}\n\n"
            f"Notable quotes pool:\n" + "\n".join(f"- {q}" for q in all_quotes[:20]) + "\n\n"
            "Call write_sections() to draft all report sections: "
            "executive_summary, methodology, key_findings, pain_points, "
            "positive_highlights, recommendations (with priorities), notable_quotes, research_gaps."
        )
        logger.info("[AnalysisAgent] Pass 3 complete: sections written")

        # ── Pass 4: self_critique then finalize ──────────────────────────────
        self.reset()
        await self.run(
            context_header +
            f"Report sections are drafted. Patterns confirmed from {n} transcripts.\n\n"
            "Call self_critique() to identify gaps and weak claims, then "
            "call finalize_report() with quality rating and tldr summary."
        )
        logger.info("[AnalysisAgent] Pass 4 complete: critique and finalized")

        return self.final_report or {}
