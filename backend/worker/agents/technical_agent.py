"""
Technical agent -- same shape as fundamentals_agent.py: fetching technical
indicators is always required, never a judgment call, so this fetches
directly and uses a single run_synthesis() call for the narrative.

Phase 10, Stage C -- same synchronous-yfinance-call bug as
fundamentals_agent.py, found the same way (a real trace showing this
"parallel" branch taking as long as its blocking siblings). See that
file's docstring for the full story.
"""
import asyncio
from agent_harness import run_synthesis
from tools.technical_indicators import fetch_technical_indicators

SYSTEM_PROMPT = (
    "You are a technical analysis agent. You will be given a stock's current "
    "price, 20-day and 50-day simple moving averages, and its 14-day RSI. Give "
    "a brief, factual assessment of recent price momentum -- whether the price "
    "is trending above or below its moving averages, and whether RSI suggests "
    "overbought (>70) or oversold (<30) conditions. Be concise -- 2-3 sentences."
)


async def run(ticker: str, market: str) -> dict:
    data = await asyncio.to_thread(fetch_technical_indicators, ticker, market)
    if "error" in data:
        return {"status": "error", "error": data["error"], "data": data}

    user_message = (
        f"Ticker: {data['ticker']} ({data['resolved_symbol']})\n"
        f"Current price: {data['current_price']}\n"
        f"20-day SMA: {data['sma_20']}\n"
        f"50-day SMA: {data['sma_50']}\n"
        f"14-day RSI: {data['rsi_14']}"
    )
    result = await run_synthesis(SYSTEM_PROMPT, user_message)
    result["data"] = data
    return result
