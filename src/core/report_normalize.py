"""
report_normalize.py — Coerce a report dict into a stable shape for export.

Gemini sometimes returns list fields as plain strings (e.g. pain_points as a
list of strings) and sometimes as list of dicts. The PPTX/PDF generators call
`.get()` on each item, which crashes on a string. This normalizer converts any
string item in a known list field into a dict keyed by the field the generators
read, so exports never break on a shape mismatch.
"""

from typing import Dict, List

# field name → the dict key the generators read for a string item
_LIST_FIELD_PRIMARY_KEY: Dict[str, str] = {
    "pain_points":         "pain_point",
    "positive_highlights": "highlight",
    "recommendations":     "recommendation",
    "key_themes":          "theme",
    "opportunity_matrix":  "recommendation",
    "notable_quotes":      "quote",
    "personas":            "name",
    "emotional_journey":   "stage",
}


def normalize_report(report: dict) -> dict:
    """Return a shallow copy of the report with list fields coerced to dict items."""
    if not isinstance(report, dict):
        return report
    out = dict(report)
    for field, primary_key in _LIST_FIELD_PRIMARY_KEY.items():
        value = out.get(field)
        if not isinstance(value, list):
            continue
        coerced: List[dict] = []
        for item in value:
            if isinstance(item, dict):
                coerced.append(item)
            elif item is None:
                continue
            else:
                coerced.append({primary_key: str(item)})
        out[field] = coerced
    return out
