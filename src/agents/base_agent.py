"""
BaseAgent — Gemini function-calling loop engine.

Uses the modern google-genai SDK (replaces deprecated vertexai SDK).

Auth priority:
  1. GEMINI_API_KEY in .env  → Google AI Studio (free, no Vertex quota needed)
  2. Vertex AI ADC           → Application Default Credentials via gcloud

Get a free API key at: https://aistudio.google.com/app/apikey
Then add to .env:  GEMINI_API_KEY=AIza...
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from google import genai
from google.genai import types

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    """Describes a tool the agent can call."""
    name: str
    description: str
    parameters: Dict[str, Any]   # JSON Schema object
    handler: Callable             # sync or async callable


@dataclass
class AgentResult:
    """Return value from a full agent run."""
    text: str
    tool_calls: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


def _make_client() -> genai.Client:
    """Create a google-genai client using API key or Vertex AI ADC."""
    if settings.gemini_api_key:
        logger.debug("Gemini: using Google AI Studio API key")
        return genai.Client(api_key=settings.gemini_api_key)
    else:
        logger.debug("Gemini: using Vertex AI ADC")
        return genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_location,
        )


# Module-level shared client (created once, reset on auth failure)
_client: Optional[genai.Client] = None

def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = _make_client()
    return _client

def reset_client():
    """Force a new client on the next call — use after re-authentication."""
    global _client
    _client = None


class BaseAgent:
    """
    Base class for all GetHeard agents.

    Subclass and:
      1. Set self.name and self.system_prompt in __init__
      2. Call register_tool() for each capability
      3. Call run(message) to execute with tool loop
      4. Call chat(message) for simple conversational turns (no tools)
    """

    MAX_ITERATIONS = 15

    def __init__(self):
        self.name = "BaseAgent"
        self.system_prompt = "You are a helpful assistant."
        self.model = settings.gemini_model  # subclasses override this
        self._tool_specs: List[ToolSpec] = []
        self._tool_handlers: Dict[str, Callable] = {}
        self._history: List[types.Content] = []

    # ── Registration ─────────────────────────────────────────────────────────

    def register_tool(self, spec: ToolSpec):
        self._tool_specs.append(spec)
        self._tool_handlers[spec.name] = spec.handler

    def reset(self):
        self._history = []

    # ── Build config ──────────────────────────────────────────────────────────

    def _build_tools(self) -> Optional[List[types.Tool]]:
        if not self._tool_specs:
            return None
        declarations = [
            types.FunctionDeclaration(
                name=spec.name,
                description=spec.description,
                parameters=spec.parameters,
            )
            for spec in self._tool_specs
        ]
        return [types.Tool(function_declarations=declarations)]

    def _config(self, extra: Dict = None) -> types.GenerateContentConfig:
        cfg = {
            "system_instruction": self.system_prompt,
        }
        tools = self._build_tools()
        if tools:
            cfg["tools"] = tools
        if extra:
            cfg.update(extra)
        return types.GenerateContentConfig(**cfg)

    # ── Core loop ─────────────────────────────────────────────────────────────

    async def run(self, message: str) -> AgentResult:
        """
        Send a message and execute the full tool-calling loop until the agent
        produces a plain text response (no more function calls).
        """
        client = get_client()
        model = self.model
        config = self._config()

        # Add user message to history
        self._history.append(
            types.Content(role="user", parts=[types.Part(text=message)])
        )

        tool_call_log: List[Dict] = []
        iterations = 0

        while iterations < self.MAX_ITERATIONS:
            iterations += 1

            try:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model,
                    contents=self._history,
                    config=config,
                )
            except Exception as exc:
                if "Reauthentication" in str(exc) or "RefreshError" in type(exc).__name__:
                    reset_client()
                raise

            candidate = response.candidates[0]
            # Add model response to history
            self._history.append(candidate.content)

            # Collect function calls
            func_calls = [
                p.function_call
                for p in candidate.content.parts
                if p.function_call is not None
            ]

            if not func_calls:
                # No tool calls — extract text
                text = "".join(
                    p.text for p in candidate.content.parts if hasattr(p, "text") and p.text
                )
                return AgentResult(text=text, tool_calls=tool_call_log)

            # Execute each tool call and collect results
            result_parts: List[types.Part] = []
            for fc in func_calls:
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}
                logger.info(f"[{self.name}] → {tool_name}({list(tool_args.keys())})")

                handler = self._tool_handlers.get(tool_name)
                if handler is None:
                    result = {"error": f"Unknown tool: {tool_name}"}
                else:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            result = await handler(**tool_args)
                        else:
                            result = await asyncio.to_thread(handler, **tool_args)
                    except Exception as exc:
                        logger.error(f"[{self.name}] Tool {tool_name} raised: {exc}")
                        result = {"error": str(exc)}

                if not isinstance(result, dict):
                    result = {"result": str(result)}

                tool_call_log.append({"tool": tool_name, "args": tool_args, "result": result})
                result_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(name=tool_name, response=result)
                    )
                )

            # Add tool results to history and continue
            self._history.append(
                types.Content(role="user", parts=result_parts)
            )

        logger.warning(f"[{self.name}] Reached MAX_ITERATIONS ({self.MAX_ITERATIONS})")
        return AgentResult(text="Analysis incomplete — max iterations reached.", tool_calls=tool_call_log)

    async def chat(self, message: str) -> str:
        """Simple conversational turn — no tool loop, maintains history."""
        client = get_client()
        self._history.append(
            types.Content(role="user", parts=[types.Part(text=message)])
        )
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=self.model,
            contents=self._history,
            config=self._config(),
        )
        reply_text = response.text or ""
        self._history.append(
            types.Content(role="model", parts=[types.Part(text=reply_text)])
        )
        return reply_text
