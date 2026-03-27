"""
Transcript storage - saves interview conversations to JSON files.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

TRANSCRIPTS_DIR = Path(__file__).parent.parent.parent / "transcripts"


class TranscriptManager:
    """Manages saving and loading of interview transcripts."""

    def __init__(self, transcripts_dir: Optional[Path] = None):
        self.transcripts_dir = transcripts_dir or TRANSCRIPTS_DIR
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        session_id: str,
        language_code: str,
        conversation: List[Dict],
        metadata: Optional[Dict] = None,
    ) -> str:
        """Save interview transcript to a JSON file. Returns file path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{session_id}_{language_code}.json"
        filepath = self.transcripts_dir / filename

        data = {
            "session_id": session_id,
            "language_code": language_code,
            "started_at": metadata.get("started_at") if metadata else None,
            "ended_at": datetime.now().isoformat(),
            "metadata": metadata or {},
            "conversation": conversation,
            "turn_count": len(conversation),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Transcript saved: {filepath}")
        return str(filepath)

    def load(self, filepath: str) -> Dict:
        """Load transcript from file."""
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_transcripts(self) -> List[Dict]:
        """List all saved transcripts with summary metadata."""
        results = []
        for f in sorted(self.transcripts_dir.glob("*.json"), reverse=True):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                results.append({
                    "file": f.name,
                    "session_id": data.get("session_id"),
                    "language_code": data.get("language_code"),
                    "ended_at": data.get("ended_at"),
                    "turn_count": data.get("turn_count", 0),
                })
            except Exception:
                pass
        return results
