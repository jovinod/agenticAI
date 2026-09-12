from typing import Any

MIN_ROE_PCT = 8
MAX_DEBT_TO_EQUITY = 200
RECENT_YEARS_CHECKED = 2


def check_hard_stop_rules(extended_data: dict[str, Any]) -> list[str]:
    """Pure comparisons against trusted, already-fetched data. Missing
    data does not trigger a stop -- that avoids equating unknown with
    failed, though it also means a recommendation can proceed with
    incomplete evidence."""
    stops: list[str] = []

    roe = extended_data.get("roe")
    if roe is not None and roe * 100 < MIN_ROE_PCT:
        stops.append("Return on equity is below the quality floor.")

    debt_to_equity = extended_data.get("debt_to_equity")
    if debt_to_equity is not None and debt_to_equity > MAX_DEBT_TO_EQUITY:
        stops.append("Debt-to-equity exceeds the leverage ceiling.")

    free_cash_flow_history = extended_data.get("free_cash_flow_history") or []
    recent_fcf = free_cash_flow_history[:RECENT_YEARS_CHECKED]
    if recent_fcf and any(value < 0 for value in recent_fcf):
        stops.append("Free cash flow was negative in a recent reported year.")

    return stops
