"""
DesignerAgent — Interview guide designer with self-review and revision loop.

This agent is categorically different from the one-shot generate_questions() in
research_project.py. It runs a full quality loop:

  1. generate_draft()      — produces an initial question set
  2. review_questions()    — critiques each question for quality issues
  3. revise_question()     — rewrites specific weak questions (repeatable)
  4. finalize()            — marks the set as ready

The Gemini model decides how many revision passes to make based on review feedback.
It stops when it's satisfied all questions meet the quality bar.

Usage:
    agent = DesignerAgent(brief_dict)
    questions = await agent.design()   # List[dict]
"""

import logging
from typing import Dict, List, Optional

from config.settings import settings
from .base_agent import BaseAgent, ToolSpec

logger = logging.getLogger(__name__)

DESIGNER_SYSTEM_PROMPT = """You are a principal qualitative research designer with 15 years of experience in Asian consumer research.

Your task: design a high-quality interview guide for the research study described in the brief.

━━ YOUR WORKFLOW (follow this order) ━━
1. generate_draft()      → Write the full question set
2. review_questions()    → Critique every question — be harsh, not lenient
3. revise_question()     → Fix each issue found (call once per question that needs fixing)
4. review_questions()    → Re-review after revisions (only if you made significant changes)
5. finalize()            → Mark complete only when all questions are high quality

━━ QUESTION QUALITY CRITERIA ━━
A good question:
  ✓ Open-ended (cannot be answered yes/no)
  ✓ Specific enough to generate actionable stories
  ✓ Non-leading (does not imply a desired answer)
  ✓ Culturally appropriate for the target audience and language
  ✓ Has a natural follow-up probe that digs deeper
  ✓ Serves a clear research intent tied to the objective

Common issues to catch:
  ✗ "Do you like X?" → leading and yes/no
  ✗ "Why don't you use X?" → assumes they don't
  ✗ Double-barrelled: two questions in one ("how many steps AND how long AND what did you feel?")
  ✗ Jargon the respondent may not understand
  ✗ Too abstract ("Tell me about your life")
  ✗ Duplicates: two questions covering the same ground
  ✗ Too long: any question over 20 words is too long — split or simplify
  ✗ Multi-part: asking for process + duration + opinion in one breath — pick ONE angle per question

━━ VOICE INTERVIEW CONSTRAINTS ━━
These questions will be asked VERBALLY. This means:
  • Each question must be speakable in under 10 seconds
  • Maximum 15 words per question
  • ONE focus per question — never combine steps, duration, and opinion
  • The probe should invite a story, not a list ("What happened next?" not "Please describe each step")
  • Avoid questions that sound like a form ("On a scale of 1-10...")

━━ QUESTION FLOW ━━
Start with rapport-building (opening), move to behavioral recall (experience),
explore emotions, then satisfaction and improvement, close with forward-looking thoughts.

━━ QUESTION TYPES ━━
  opening     → warm-up, build rapport
  experience  → "Tell me about a time when..." (behavioral recall)
  emotional   → feelings, reactions, perceptions
  satisfaction → how well needs are being met
  improvement → what would make it better
  closing     → final thoughts, recommendations, anything else to share

Be rigorous. A weak interview guide produces weak data."""


class DesignerAgent(BaseAgent):
    """
    Produces a reviewed, revised, finalized set of interview questions.

    Attributes:
        final_questions: List[Dict] — available after design() completes
        review_history: List of review passes with issues found
    """

    def __init__(self, brief: Dict):
        super().__init__()
        self.name = "DesignerAgent"
        self.model = settings.gemini_model_pro  # pro — quality question generation + self-review
        self.system_prompt = DESIGNER_SYSTEM_PROMPT
        self.brief = brief

        self._draft_questions: List[Dict] = []
        self.review_history: List[Dict] = []
        self.final_questions: Optional[List[Dict]] = None
        self._finalize_summary: str = ""

        self._register_tools()

    # ── Tool registration ────────────────────────────────────────────────────

    def _register_tools(self):
        self.register_tool(ToolSpec(
            name="generate_draft",
            description="Store the initial draft of interview questions. Call this first.",
            parameters={
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "description": "Complete list of interview questions",
                        "items": {
                            "type": "object",
                            "properties": {
                                "number":  {"type": "integer", "description": "Question number starting at 1"},
                                "type":    {"type": "string", "enum": ["opening", "experience", "emotional", "satisfaction", "improvement", "closing"]},
                                "main":    {"type": "string", "description": "The main interview question asked to the respondent"},
                                "probe":   {"type": "string", "description": "A follow-up probe to deepen the answer"},
                                "intent":  {"type": "string", "description": "What this question is designed to uncover"},
                            },
                            "required": ["number", "type", "main", "probe", "intent"],
                        },
                    },
                },
                "required": ["questions"],
            },
            handler=self._generate_draft_handler,
        ))

        self.register_tool(ToolSpec(
            name="review_questions",
            description=(
                "Review all current questions and log quality issues. "
                "If no issues are found, pass an empty issues list. "
                "Be strict — this is the quality gate."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "issues": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question_number": {"type": "integer"},
                                "issue_type": {
                                    "type": "string",
                                    "enum": ["leading", "yes_no", "double_barrelled", "vague", "duplicate", "jargon", "culturally_inappropriate", "other"],
                                },
                                "description": {"type": "string", "description": "Specific description of the problem"},
                                "suggested_rewrite": {"type": "string", "description": "Suggested improved version"},
                            },
                            "required": ["question_number", "issue_type", "description", "suggested_rewrite"],
                        },
                    },
                    "overall_assessment": {
                        "type": "string",
                        "description": "Brief overall quality assessment of the draft",
                    },
                },
                "required": ["issues", "overall_assessment"],
            },
            handler=self._review_questions_handler,
        ))

        self.register_tool(ToolSpec(
            name="revise_question",
            description="Rewrite a specific question to fix a quality issue. Call once per question being revised.",
            parameters={
                "type": "object",
                "properties": {
                    "question_number": {"type": "integer"},
                    "new_main":   {"type": "string", "description": "Improved question text"},
                    "new_probe":  {"type": "string", "description": "Improved probe text"},
                    "new_intent": {"type": "string", "description": "Updated intent (if changed)"},
                    "change_reason": {"type": "string", "description": "What specific issue this fixes"},
                },
                "required": ["question_number", "new_main", "new_probe", "new_intent", "change_reason"],
            },
            handler=self._revise_question_handler,
        ))

        self.register_tool(ToolSpec(
            name="finalize",
            description=(
                "Mark the question set as finalised and ready for interviews. "
                "Only call this when all questions have passed quality review."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "quality_summary": {
                        "type": "string",
                        "description": "Summary of the final question set: coverage, flow, and quality",
                    },
                    "revisions_made": {
                        "type": "integer",
                        "description": "Total number of individual question revisions made",
                    },
                },
                "required": ["quality_summary", "revisions_made"],
            },
            handler=self._finalize_handler,
        ))

    # ── Tool handlers ────────────────────────────────────────────────────────

    async def _generate_draft_handler(self, questions: List[Dict]) -> Dict:
        self._draft_questions = questions
        logger.info(f"[DesignerAgent] Draft generated: {len(questions)} questions")
        return {
            "status": "draft_stored",
            "count": len(questions),
            "next_step": "Call review_questions() to quality-check each question",
        }

    async def _review_questions_handler(self, issues: List[Dict], overall_assessment: str) -> Dict:
        review_entry = {
            "pass": len(self.review_history) + 1,
            "issues": issues,
            "overall": overall_assessment,
        }
        self.review_history.append(review_entry)
        logger.info(f"[DesignerAgent] Review pass {review_entry['pass']}: {len(issues)} issues found")

        if not issues:
            return {
                "status": "all_clear",
                "message": "All questions pass quality review. Call finalize() now.",
            }
        return {
            "status": "issues_found",
            "count": len(issues),
            "next_step": f"Call revise_question() for each of the {len(issues)} issues, then review again.",
        }

    async def _revise_question_handler(
        self,
        question_number: int,
        new_main: str,
        new_probe: str,
        new_intent: str,
        change_reason: str,
    ) -> Dict:
        for q in self._draft_questions:
            if q.get("number") == question_number:
                old_main = q["main"]
                q["main"] = new_main
                q["probe"] = new_probe
                q["intent"] = new_intent
                logger.info(
                    f"[DesignerAgent] Q{question_number} revised: "
                    f'"{old_main[:45]}…" → "{new_main[:45]}…"'
                )
                return {
                    "status": "revised",
                    "question_number": question_number,
                    "reason": change_reason,
                }
        return {"error": f"Question {question_number} not found in draft"}

    async def _finalize_handler(self, quality_summary: str, revisions_made: int) -> Dict:
        self.final_questions = list(self._draft_questions)
        self._finalize_summary = quality_summary
        logger.info(
            f"[DesignerAgent] Finalized {len(self.final_questions)} questions "
            f"({revisions_made} revisions made)"
        )
        return {
            "status": "finalized",
            "count": len(self.final_questions),
            "quality_summary": quality_summary,
        }

    # ── Public interface ─────────────────────────────────────────────────────

    async def design(self) -> List[Dict]:
        """
        Run the full design loop and return the finalized question list.
        The agent will generate, review, revise (possibly multiple times), and finalize.
        """
        audience = self.brief.get("target_audience") or self.brief.get("audience", "General consumers")
        topics_list = self.brief.get("topics", [])
        topics_str = ", ".join(topics_list) if topics_list else "Not specified"

        prompt = f"""Research Brief:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Project:          {self.brief.get('project_name', 'Untitled')}
Research Type:    {self.brief.get('research_type', 'cx').upper()}
Industry:         {self.brief.get('industry', 'Not specified')}
Objective:        {self.brief.get('objective', 'Not specified')}
Target Audience:  {audience}
Interview Language: {self.brief.get('language', 'en')}
Key Topics:       {topics_str}
Question Count:   {self.brief.get('question_count', 10)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Please design the interview guide now.
Follow the workflow: generate_draft → review_questions → revise any weak questions → finalize.
Do not skip the review step."""

        await self.run(prompt)

        # Return finalized questions if available, fall back to draft
        return self.final_questions or self._draft_questions
