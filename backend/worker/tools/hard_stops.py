"""
Hard-stop rules for the Decision agent -- pure Python, no LLM involvement,
by design (see book/chapter-08-auth.md, Section F.6: "route pure arithmetic
to arithmetic"). Each rule here is a fact-check on a real number, not a
judgment call, so there's nothing for a model to reason about -- and an
LLM is a worse tool than a comparison operator for exactly this kind of
check (it can misread a figure, or be nudged by unrelated context).

Adapted from buynobuy's real hard-stop config (skills/master/
orchestration.json), but recalibrated to what yfinance actually provides
for BOTH US and India tickers -- buynobuy's original thresholds (ROE/ROCE
< 12%, promoter pledging, etc.) come from India-specific Trendlyne data
this project doesn't have. These three are a starting set, not a claim
that they're the final right thresholds.
"""

MIN_ROE_PCT = 8.0
MAX_DEBT_TO_EQUITY = 200.0  # yfinance's own units (a ratio x100, e.g. 78.4 means 0.784x)


def check_hard_stop_rules(extended_data: dict) -> list[str]:
    """Returns a list of triggered hard-stop descriptions -- empty means
    none triggered. Never invoked by the model; called directly in Python
    and force-set onto the Decision agent's result regardless of what the
    model's own output said, per the F.6 pattern."""
    if "error" in extended_data:
        return []  # nothing to check without real data -- not itself a stop

    stops = []

    roe = extended_data.get("return_on_equity")
    if roe is not None and roe * 100 < MIN_ROE_PCT:
        stops.append(f"Return on equity {roe * 100:.1f}% is below the {MIN_ROE_PCT:.0f}% quality floor.")

    debt_to_equity = extended_data.get("debt_to_equity")
    if debt_to_equity is not None and debt_to_equity > MAX_DEBT_TO_EQUITY:
        stops.append(f"Debt-to-equity {debt_to_equity:.0f} exceeds the {MAX_DEBT_TO_EQUITY:.0f} leverage ceiling.")

    fcf_history = extended_data.get("fcf_history") or {}
    recent_years = sorted(fcf_history.keys())[-2:]  # yfinance reliably gives ~4 years -- check the 2 most recent
    recent_fcf = [fcf_history[y] for y in recent_years]
    if recent_fcf and all(v < 0 for v in recent_fcf):
        stops.append(f"Free cash flow has been negative for the {len(recent_fcf)} most recent reported year(s).")

    return stops
