"""
Decision agent -- replaces Synthesizer as the graph's final node. Unlike
every other agent here except News, this one runs a real tool-calling loop:
given Fundamentals/Technical/News/Risk's summaries (and, if it ran, Devil's
Advocate's counter-thesis), it decides turn by turn whether it needs to
compute intrinsic value, check hard stops, or whether it already has enough
to conclude -- genuine tool-choice, not "always call these in order."

The two tools take NO arguments from the model on purpose: compute_
intrinsic_value needs multi-year EPS/price history, and an LLM asked to
transcribe that as JSON tool-call arguments would be an unreliable, wasteful
way to move data the agent process already has in memory. Both tools are
closures over data fetched before the loop starts (see run()) -- the model
just decides WHETHER to call them, not what to pass.

Hard-stop determination itself is deliberately NOT part of the loop's own
judgment -- see the F.6 pattern in book/chapter-08-auth.md: computed here in
plain Python, and force-set onto the final result after the model runs,
regardless of what the model's own text said. The model's real job is
weighing the narrative signals and the hard-stop RESULT together, not
re-deriving whether a hard stop fired.
"""
import asyncio
from agent_harness import run_agent
from tools.extended_fundamentals import fetch_extended_fundamentals
from tools.valuation import compute_intrinsic_value
from tools.hard_stops import check_hard_stop_rules
from llm.parse_json import parse_llm_json

SYSTEM_PROMPT = (
    "You are the final decision-maker for a stock research report. You will be given "
    "fundamentals, technical, news, and risk assessments, and optionally a Devil's "
    "Advocate counter-thesis. Decide whether you need to compute the stock's intrinsic "
    "value or check deterministic hard-stop rules before you can responsibly conclude -- "
    "call those tools if so, or go straight to a conclusion if the other assessments "
    "already give you enough. "
    "Weigh all available signals, including the Devil's Advocate counter-thesis if "
    "present, and reach a final recommendation. "
    "Respond with ONLY a JSON object: "
    '{"recommendation": "BUY|HOLD|SELL", "overall_score": <1-10>, '
    '"summary": "<3-4 sentences citing the specific numbers that drove this>"}'
)


async def run(
    ticker: str,
    market: str,
    fundamentals_summary: str,
    technical_summary: str,
    news_summary: str,
    risk_summary: str,
    devil_advocate_summary: str = "",
) -> dict:
    # Phase 10, Stage C -- same synchronous-yfinance blocking bug as
    # fundamentals_agent.py/technical_agent.py, found via a real trace.
    # Decision runs sequentially (no concurrent sibling to stall) so this
    # specific call site never produced the "parallel branches all block on
    # each other" symptom those two did -- fixed anyway for consistency, and
    # because it shortens Decision's own wall-clock time regardless.
    extended_data = await asyncio.to_thread(fetch_extended_fundamentals, ticker, market)

    async def compute_intrinsic_value_tool():
        return compute_intrinsic_value(
            extended_data.get("eps_history", {}),
            extended_data.get("monthly_prices"),
            extended_data.get("current_price"),
        )

    async def check_hard_stop_rules_tool():
        return {"hard_stops_triggered": check_hard_stop_rules(extended_data)}

    tool_schemas = [
        {
            "type": "function",
            "function": {
                "name": "compute_intrinsic_value",
                "description": (
                    "Compute this stock's intrinsic value from historical P/E, "
                    "including a best-case and worst-case price target and a "
                    "margin-of-safety verdict."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_hard_stop_rules",
                "description": (
                    "Check deterministic hard-stop rules (return on equity, "
                    "debt-to-equity, free cash flow trend) that may disqualify a BUY "
                    "recommendation regardless of the narrative."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]
    tool_registry = {
        "compute_intrinsic_value": compute_intrinsic_value_tool,
        "check_hard_stop_rules": check_hard_stop_rules_tool,
    }

    devil_block = f"\n\nDevil's Advocate counter-thesis: {devil_advocate_summary}" if devil_advocate_summary else ""
    user_message = (
        f"Ticker: {ticker}\n\n"
        f"Fundamentals: {fundamentals_summary}\n\n"
        f"Technical: {technical_summary}\n\n"
        f"News: {news_summary}\n\n"
        f"Risk: {risk_summary}"
        f"{devil_block}"
    )

    result = await run_agent(SYSTEM_PROMPT, user_message, tool_schemas, tool_registry)

    parsed, parse_err = parse_llm_json(result.get("answer", "")) if result.get("status") == "success" else ({}, "loop did not conclude")
    if parse_err:
        parsed = {"recommendation": "HOLD", "overall_score": None, "summary": f"Decision synthesis failed: {parse_err}"}

    # F.6 pattern -- computed in Python, never inferred by the model, and set
    # here regardless of whether the model called check_hard_stop_rules at all.
    parsed["hard_stops_triggered"] = check_hard_stop_rules(extended_data)
    parsed["intrinsic_value"] = compute_intrinsic_value(
        extended_data.get("eps_history", {}),
        extended_data.get("monthly_prices"),
        extended_data.get("current_price"),
    )
    parsed["usage"] = result.get("usage", {})
    parsed["answer"] = parsed.get("summary", "")  # graph.py reads "answer" the same way every other agent's result does
    return parsed
