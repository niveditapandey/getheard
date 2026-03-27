"""
GetHeard Multi-Agent Architecture
==================================

Five discrete agents, each with a specific role in the research pipeline:

  BriefAgent       → Conversational intake, collects research brief via chat
  DesignerAgent    → Generates + self-reviews + revises interview questions
  InterviewAgent   → Conducts voice interviews with contextual probing decisions
  AnalysisAgent    → 4-pass transcript analysis (extract → synthesize → write → critique)
  Orchestrator     → Coordinates the full pipeline end-to-end

All agents extend BaseAgent which implements a Gemini function-calling loop:
  user message → Gemini decides tool to call → tool executes → result fed back → repeat
"""

from .base_agent import BaseAgent, AgentResult, ToolSpec
from .brief_agent import BriefAgent
from .designer_agent import DesignerAgent
from .interview_agent import InterviewAgent
from .analysis_agent import AnalysisAgent
from .orchestrator import Orchestrator

__all__ = [
    "BaseAgent",
    "AgentResult",
    "ToolSpec",
    "BriefAgent",
    "DesignerAgent",
    "InterviewAgent",
    "AnalysisAgent",
    "Orchestrator",
]
