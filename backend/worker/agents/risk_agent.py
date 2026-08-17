"""
Risk agent -- doesn't fetch anything new. Takes the deterministic
flag_risk_factors output (Chapter 3, unchanged) plus the three other agents'
narrative summaries, and makes ONE genuine judgment call weighing all four
signals together. This is the first agent in this project where the LLM's
synthesis is actually load-bearing, not just a nice-to-have narrative layer
on top of numbers that already spoke for themselves.
"""
from agent_harness import run_synthesis
from skills.flag_risk_factors.flag_risk_factors import flag_risk_factors

SYSTEM_PROMPT = (
    "You are a risk assessment agent. You will be given: deterministic risk "
    "flags computed from real financial data, plus separate fundamentals, "
    "technical, and news assessments from other analysts. Weigh all four "
    "together and give a brief, honest overall risk judgment -- note "
    "specifically when multiple signals point the same direction (a stronger "
    "signal) versus when they conflict. Be concise -- 3-4 sentences."
)


async def run(fundamentals_data: dict, fundamentals_summary: str, technical_summary: str, news_summary: str) -> dict:
    flags = flag_risk_factors(fundamentals_data) if "error" not in fundamentals_data else []

    user_message = (
        f"Deterministic risk flags: {flags if flags else 'none triggered'}\n\n"
        f"Fundamentals assessment: {fundamentals_summary}\n\n"
        f"Technical assessment: {technical_summary}\n\n"
        f"News assessment: {news_summary}"
    )
    result = await run_synthesis(SYSTEM_PROMPT, user_message)
    result["flags"] = flags
    return result
