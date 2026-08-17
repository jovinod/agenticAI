"""
Fundamentals agent -- no tool-choice involved (fetching fundamentals is
always required, never a judgment call), so this fetches directly and uses
a single run_synthesis() call for the narrative, not the full tool-calling
loop. See agent_harness.py's run_synthesis docstring for why.
"""
from agent_harness import run_synthesis
from tools.stock_data import fetch_stock_data

SYSTEM_PROMPT = (
    "You are a fundamentals research agent. You will be given a stock's current "
    "price, P/E ratio, market cap, and 52-week range. Give a brief, factual "
    "assessment of the company's current valuation and financial standing based "
    "on those numbers. Be concise -- 2-3 sentences."
)


async def run(ticker: str, market: str) -> dict:
    data = fetch_stock_data(ticker, market)
    if "error" in data:
        return {"status": "error", "error": data["error"], "data": data}

    user_message = (
        f"Ticker: {data['ticker']} ({data['resolved_symbol']})\n"
        f"Price: {data['currency']} {data['price']}\n"
        f"P/E ratio: {data['pe_ratio']}\n"
        f"Market cap: {data['market_cap']}\n"
        f"52-week range: {data['fifty_two_week_low']}-{data['fifty_two_week_high']}"
    )
    result = await run_synthesis(SYSTEM_PROMPT, user_message)
    result["data"] = data
    return result
