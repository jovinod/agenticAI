"""
Synthesizer agent -- the last node in the graph. Takes every other agent's
output and produces the final report text a user actually reads. No new
data, no tool choice -- purely a writing/combining job.
"""
from agent_harness import run_synthesis

SYSTEM_PROMPT = (
    "You are a research report synthesizer. You will be given separate "
    "fundamentals, technical, news, and risk assessments for a stock. Combine "
    "them into one coherent report a real investor could read in under a "
    "minute: a one-line headline judgment, then a short paragraph per section. "
    "Do not repeat numbers verbatim across sections -- synthesize, don't paste."
)


async def run(ticker: str, fundamentals_summary: str, technical_summary: str, news_summary: str, risk_summary: str) -> dict:
    user_message = (
        f"Ticker: {ticker}\n\n"
        f"Fundamentals: {fundamentals_summary}\n\n"
        f"Technical: {technical_summary}\n\n"
        f"News: {news_summary}\n\n"
        f"Risk: {risk_summary}"
    )
    return await run_synthesis(SYSTEM_PROMPT, user_message)
