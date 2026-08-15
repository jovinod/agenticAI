"""
A Skill — a reusable capability module any agent can load, distinct from a
"tool" (an LLM decides at runtime to call it) and a "direct API call" (our
code always calls it, no judgment involved). This one is pure Python, no LLM
needed at all — an honest example that a Skill doesn't require an LLM to be
useful.

Pulled forward from Phase 5 slightly (see project-structure.md's target
layout), same pattern already used for the caching work earlier this project.
"""


def flag_risk_factors(stock_data: dict) -> list[str]:
    """Given tools.stock_data.fetch_stock_data()'s output, return simple rule-based risk flags."""
    flags = []

    price = stock_data.get("price")
    low = stock_data.get("fifty_two_week_low")
    high = stock_data.get("fifty_two_week_high")
    pe = stock_data.get("pe_ratio")

    if price and low and high and high > low:
        position_in_range = (price - low) / (high - low)
        if position_in_range < 0.1:
            flags.append("Price is near its 52-week low")

    if pe is not None:
        if pe < 0:
            flags.append("Negative P/E ratio — company is currently unprofitable")
        elif pe > 40:
            flags.append(f"P/E ratio ({pe:.1f}) is high — richly valued relative to typical norms")

    return flags
