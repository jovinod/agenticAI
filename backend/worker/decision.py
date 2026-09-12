import json
from typing import Any

from hard_stops import check_hard_stop_rules
from valuation import compute_intrinsic_value


def _parse_model_output(raw_content: str) -> dict[str, Any]:
    """Parse failure falls back to HOLD, no score, and a visible
    synthesis error -- protecting the state shape, not the quality of
    the underlying evidence."""
    try:
        parsed = json.loads(raw_content)
        return {
            "recommendation": parsed.get("recommendation", "HOLD"),
            "overall_score": parsed.get("overall_score"),
            "summary": parsed.get("summary", ""),
        }
    except (json.JSONDecodeError, TypeError):
        return {
            "recommendation": "HOLD",
            "overall_score": None,
            "summary": "synthesis error: could not parse model output",
        }


def make_decision(raw_model_content: str, extended_data: dict[str, Any]) -> dict[str, Any]:
    """After the model loop, the application recomputes deterministic
    fields and overwrites those result keys -- guaranteeing the stored
    calculations come from Python. It does NOT guarantee the
    recommendation obeys them: current code can retain BUY while
    attaching a nonempty hard-stop list. That is a real, documented gap,
    not a bug this function silently patches over.
    """
    parsed = _parse_model_output(raw_model_content)

    parsed["hard_stops_triggered"] = check_hard_stop_rules(extended_data)
    parsed["intrinsic_value"] = compute_intrinsic_value(
        extended_data.get("eps_history", {}),
        extended_data.get("monthly_prices"),
        extended_data.get("current_price"),
    )

    return parsed
