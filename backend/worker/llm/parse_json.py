"""
Parsing a model's final answer as structured JSON -- needed by Decision and
Devil's Advocate, the first two agents here whose final output is a typed
object rather than free-form narrative text. Adapted from buynobuy's
agents/utils.py::parse_llm_json, a real, already-proven pattern for this
exact problem (models sometimes wrap JSON in markdown fences or add stray
prose despite being told not to).
"""
import json
import re


def parse_llm_json(raw: str) -> tuple[dict, str | None]:
    """Returns (parsed_dict, None) on success, or ({}, error_message) on failure."""
    cleaned = re.sub(r"^```[a-z]*\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        start, end = cleaned.index("{"), cleaned.rindex("}") + 1
        cleaned = cleaned[start:end]
    except ValueError:
        pass
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError as exc:
        return {}, f"JSON parse failed: {exc} -- raw ({len(raw)} chars): {raw[:300]}"
