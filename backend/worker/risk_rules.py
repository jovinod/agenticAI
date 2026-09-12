from typing import Any

NEAR_LOW_THRESHOLD = 0.1
HIGH_PE_THRESHOLD = 40


def flag_risk_factors(data: dict[str, Any]) -> list[str]:
    """Fixed, inspectable rules -- no model judgment involved.

    Teaching thresholds, not financial truths: transparent, deterministic,
    and easy to test with constructed data.
    """
    flags: list[str] = []

    price = data.get("price")
    low = data.get("fifty_two_week_low")
    high = data.get("fifty_two_week_high")
    if price is not None and low is not None and high is not None and high != low:
        position = (price - low) / (high - low)
        if position < NEAR_LOW_THRESHOLD:
            flags.append("near_52_week_low")

    pe_ratio = data.get("pe_ratio")
    if pe_ratio is not None:
        if pe_ratio < 0:
            flags.append("unprofitable")
        elif pe_ratio > HIGH_PE_THRESHOLD:
            flags.append("high_pe_ratio")

    return flags


def format_ticker_result(data: dict[str, Any], flags: list[str]) -> dict[str, Any]:
    return {**data, "flags": flags}
