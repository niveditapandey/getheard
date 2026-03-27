"""
Gemini conversation engine - supports both default 3-question mode
and custom project question sets (5–30 questions).
"""

import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

from google import genai
from google.genai import types

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from src.conversation.prompts import (
    CLOSING_TEMPLATE_EN,
    INTERVIEWER_SYSTEM_PROMPT,
    get_closing,
    get_greeting,
    get_question,
)

LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi", "id": "Indonesian",
    "fil": "Filipino", "th": "Thai", "vi": "Vietnamese",
    "ko": "Korean", "ja": "Japanese", "zh": "Mandarin Chinese",
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GeminiInterviewer:
    """
    Manages multi-language interviews using Gemini.

    Pass `custom_questions` (list of dicts with 'main' and 'probe' keys)
    to run a project-specific question set instead of the 3 default questions.
    """

    COMPLETED = "completed"

    def __init__(
        self,
        language_code: str = "en",
        custom_questions: Optional[List[dict]] = None,
        project_name: Optional[str] = None,
    ):
        # Build system prompt — richer when we have a project context
        system = INTERVIEWER_SYSTEM_PROMPT
        if project_name and custom_questions:
            system += (
                f"\n\nYou are conducting a research study called '{project_name}'. "
                "Follow the provided question sequence carefully. "
                "After each user response, decide whether to probe deeper or move on. "
                "You have a specific list of questions to cover — don't skip them."
            )

        # google-genai client — uses API key if set, else Vertex AI ADC
        if settings.gemini_api_key:
            self._client = genai.Client(api_key=settings.gemini_api_key)
        else:
            self._client = genai.Client(
                vertexai=True,
                project=settings.gcp_project_id,
                location=settings.gcp_location,
            )

        self._system = system
        self._chat_history: List[types.Content] = []
        self.chat = True  # flag: initialized
        self.language_code = language_code
        self.project_name = project_name

        # Custom questions override default 3
        self._custom_questions: List[dict] = custom_questions or []
        self._use_custom = bool(custom_questions)
        self._total_questions = len(custom_questions) if custom_questions else 3

        self.state = "not_started"
        self.current_question_idx = 0   # 0-based index into question list
        self._turns_on_current = 0       # AI turns given on current question
        self.conversation_history: List[Dict] = []
        self.start_time: Optional[datetime] = None

        # Pre-translate all questions now so each turn has zero translation latency
        self._translated_questions: List[dict] = []
        if self._use_custom and language_code != "en":
            self._preload_translations()

        logger.info(
            f"GeminiInterviewer | lang={language_code} | "
            f"questions={self._total_questions} | custom={self._use_custom} | "
            f"translations_cached={len(self._translated_questions)}"
        )

    # ── Public API ──────────────────────────────────────────────────────────

    def start_interview(self) -> str:
        self.state = "greeting"
        self.start_time = datetime.now()
        if self._use_custom and self.project_name:
            greeting = self._generate_project_greeting()
        else:
            greeting = get_greeting(self.language_code)
        self._record("interviewer", greeting)
        return greeting

    def _preload_translations(self):
        """Translate all questions + probes upfront. Called once at init so turns are instant."""
        lang_name = LANGUAGE_NAMES.get(self.language_code, "English")
        # Build one batched prompt to translate everything in a single API call
        lines = []
        for i, q in enumerate(self._custom_questions):
            lines.append(f"Q{i+1}_MAIN: {q.get('main', '')}")
            if q.get("probe"):
                lines.append(f"Q{i+1}_PROBE: {q.get('probe', '')}")
        batch = "\n".join(lines)
        try:
            resp = self._client.models.generate_content(
                model=settings.gemini_model,
                contents=(
                    f"Translate each labelled line below into {lang_name}. "
                    "Keep labels exactly as-is (Q1_MAIN:, Q1_PROBE:, etc.). "
                    "Make each translation conversational and natural. "
                    "Output only the translated lines, one per line.\n\n" + batch
                ),
            )
            output = resp.text.strip()
            # Parse back into per-question dicts
            result: dict = {}
            for line in output.splitlines():
                if ":" in line:
                    label, _, text = line.partition(":")
                    result[label.strip()] = text.strip()
            for i in range(len(self._custom_questions)):
                self._translated_questions.append({
                    "main":  result.get(f"Q{i+1}_MAIN",  self._custom_questions[i].get("main", "")),
                    "probe": result.get(f"Q{i+1}_PROBE", self._custom_questions[i].get("probe", "")),
                })
            logger.info(f"Pre-translated {len(self._translated_questions)} questions → {lang_name}")
        except Exception as e:
            logger.error(f"Batch translation failed: {e} — will translate on demand")
            self._translated_questions = []  # fall back to on-demand

    def _generate_project_greeting(self) -> str:
        """Generate a contextually correct greeting for this specific project."""
        lang_name = LANGUAGE_NAMES.get(self.language_code, "English")
        prompt = (
            f"Generate a warm, brief interview greeting in {lang_name}. "
            f"You are Alex from GetHeard, a research firm. "
            f"You are starting a research interview for a study called '{self.project_name}'. "
            "Tell the participant: their responses are confidential, there are no right/wrong answers, "
            "the interview will take about 10-15 minutes, and they can speak freely. "
            "Do NOT mention any specific industry (no hospitals, no healthcare) unless the project name makes it obvious. "
            "Write the entire greeting in the target language — no English words unless the language is English. "
            "Spell out numbers as words (do not use digits or hyphens like '5-10'). "
            "End with asking if they are ready to begin. Keep it under 80 words."
        )
        try:
            resp = self._client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )
            return resp.text.strip()
        except Exception as e:
            logger.error(f"Dynamic greeting failed, falling back to template: {e}")
            return get_greeting(self.language_code)

    def process_response(self, user_input: str) -> str:
        if self.state == "not_started":
            raise RuntimeError("Call start_interview() first.")

        self._record("respondent", user_input)

        if self.state == "greeting":
            return self._ask_question(0)

        if self.state == "questioning":
            decision = self._decide_next(user_input)
            if decision == "advance":
                next_idx = self.current_question_idx + 1
                if next_idx >= self._total_questions:
                    return self.end_interview()
                return self._ask_question(next_idx)
            elif decision == "close":
                return self.end_interview()
            else:  # probe / repeat / empathize
                return self._follow_up(user_input, decision)

        return self.end_interview()

    def end_interview(self) -> str:
        self.state = self.COMPLETED
        if self._use_custom and self.language_code != "en":
            lang_name = LANGUAGE_NAMES.get(self.language_code, "English")
            try:
                resp = self._client.models.generate_content(
                    model=settings.gemini_model,
                    contents=(
                        f"Write a warm, sincere closing statement for a research interview in {lang_name}. "
                        "Thank the participant for their time and honest feedback. "
                        "Keep it to 2-3 sentences. Output only the closing text."
                    ),
                )
                closing = resp.text.strip()
            except Exception:
                closing = get_closing(self.language_code)
        else:
            closing = get_closing(self.language_code)
        self._record("interviewer", closing)
        return closing

    def get_conversation_history(self) -> List[Dict]:
        return self.conversation_history

    # ── Private helpers ─────────────────────────────────────────────────────

    def _ask_question(self, idx: int) -> str:
        self.current_question_idx = idx
        self._turns_on_current = 0
        self.state = "questioning"

        if self._use_custom:
            # Use pre-translated cache if available, else on-demand translation
            if self._translated_questions and idx < len(self._translated_questions):
                text = self._translated_questions[idx].get("main", "")
            else:
                q = self._custom_questions[idx]
                text = q.get("main", "")
                if self.language_code != "en" and text:
                    text = self._render_in_language(text, is_probe=False)
        else:
            # Default 3-question set (1-indexed)
            text = get_question(idx + 1, self.language_code)

        self._record("interviewer", text)
        return text

    def _render_in_language(self, english_text: str, is_probe: bool = False) -> str:
        """Translate and naturalise an English question/probe into the interview language."""
        lang_name = LANGUAGE_NAMES.get(self.language_code, "English")
        role = "follow-up probe" if is_probe else "research interview question"
        try:
            prompt = (
                f"Translate this {role} into {lang_name}. "
                "Keep it conversational and natural — not stiff or formal. "
                "Output only the translated text, nothing else.\n\n"
                f"English: {english_text}"
            )
            resp = self._client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )
            return resp.text.strip()
        except Exception as e:
            logger.error(f"Translation error for '{english_text[:40]}…': {e}")
            return english_text  # fall back to English if translation fails

    def _decide_next(self, user_input: str) -> str:
        """
        Ask Gemini to read the actual response and decide what to do next.
        Returns: "probe" | "advance" | "repeat" | "empathize" | "close"
        """
        idx = self.current_question_idx
        q_text = (
            self._custom_questions[idx].get("main", "")
            if self._use_custom else get_question(idx + 1, self.language_code)
        )
        turns = self._turns_on_current
        remaining = self._total_questions - idx - 1
        lang_name = LANGUAGE_NAMES.get(self.language_code, "English")

        prompt = (
            f"You are an experienced qualitative research interviewer.\n"
            f"Interview language: {lang_name}\n"
            f"Current question ({idx+1}/{self._total_questions}): {q_text}\n"
            f"Respondent said: \"{user_input}\"\n"
            f"Follow-up turns already used on this question: {turns}\n"
            f"Questions remaining after this one: {remaining}\n\n"
            "Decide what to do next. Reply with EXACTLY one word:\n"
            "  REPEAT    — respondent asked to repeat / didn't understand / said 'huh?' or equivalent\n"
            "  PROBE     — answer is shallow, vague, or incomplete — dig deeper\n"
            "  EMPATHIZE — answer reveals frustration, pain or strong emotion — acknowledge first\n"
            "  ADVANCE   — answer is sufficiently detailed OR we've probed 2+ times already\n"
            "  CLOSE     — this was the last question and answer is complete\n\n"
            "Rules: if turns >= 3, always ADVANCE or CLOSE. If remaining == 0, use CLOSE not ADVANCE.\n"
            "Reply with only the single word decision."
        )
        try:
            resp = self._client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )
            decision = resp.text.strip().upper().split()[0]
            if decision not in ("REPEAT", "PROBE", "EMPATHIZE", "ADVANCE", "CLOSE"):
                decision = "ADVANCE" if turns >= 2 else "PROBE"
        except Exception as e:
            logger.error(f"_decide_next error: {e}")
            decision = "ADVANCE" if turns >= 2 else "PROBE"

        logger.info(f"[decide_next] Q{idx+1} turn={turns} → {decision}")
        return decision.lower()

    def _follow_up(self, user_input: str, decision: str = "probe") -> str:
        """Generate a contextual follow-up based on the decision."""
        self._turns_on_current += 1
        idx = self.current_question_idx
        lang_name = LANGUAGE_NAMES.get(self.language_code, "English")

        # Use pre-translated probe for first probe turn
        if decision == "probe" and self._turns_on_current == 1 and self._use_custom:
            if self._translated_questions and idx < len(self._translated_questions):
                probe = self._translated_questions[idx].get("probe", "").strip()
            else:
                q = self._custom_questions[idx]
                probe = q.get("probe", "").strip()
                if probe and self.language_code != "en":
                    probe = self._render_in_language(probe, is_probe=True)
            if probe:
                self._record("interviewer", probe)
                return probe

        # Build a decision-aware prompt
        q_text = (
            self._custom_questions[idx].get("main", "")
            if self._use_custom else get_question(idx + 1, self.language_code)
        )
        instructions = {
            "repeat":    f"The respondent wants you to repeat or clarify. Re-ask the question in a simpler, shorter way in {lang_name}.",
            "probe":     f"Ask a brief, specific follow-up to dig deeper into their answer. 1 sentence in {lang_name}. Do not repeat the main question.",
            "empathize": f"Acknowledge their feeling briefly and warmly, then gently invite them to continue. In {lang_name}.",
        }.get(decision, f"Ask a brief natural follow-up in {lang_name}.")

        ctx = (
            f"Question asked: {q_text}\n"
            f"Respondent said: {user_input}\n\n"
            f"{instructions}\n"
            f"CRITICAL: Respond ENTIRELY in {lang_name}. Short, conversational, human."
        )
        try:
            self._chat_history.append(types.Content(role="user", parts=[types.Part(text=ctx)]))
            resp = self._client.models.generate_content(
                model=settings.gemini_model,
                contents=self._chat_history,
                config=types.GenerateContentConfig(system_instruction=self._system),
            )
            text = resp.text.strip()
            self._chat_history.append(types.Content(role="model", parts=[types.Part(text=text)]))
        except Exception as e:
            logger.error(f"Follow-up generation error: {e}")
            text = "क्या आप थोड़ा और बता सकते हैं?" if self.language_code == "hi" else "Could you tell me a bit more?"

        self._record("interviewer", text)
        return text

    def _record(self, speaker: str, text: str):
        self.conversation_history.append({
            "speaker": speaker,
            "text": text,
            "timestamp": datetime.now().isoformat(),
            "state": self.state,
            "language": self.language_code,
            "question_idx": self.current_question_idx,
        })
