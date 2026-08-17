"""
The original Phase 4 single agent -- kept working as a thin wrapper over the
new agent_harness.py, so this refactor can be verified before any of the
Phase 5 agents (backend/worker/agents/*.py) get built on top of the same
harness. worker.py still calls this today; swapping it for the real
multi-agent graph is a later, separate step.
"""
from agent_harness import run_agent as _run_agent
from tools.stock_data import fetch_stock_data
from tools.web_search import search_via_mcp
from skills.assess_news_sentiment.skill import load_instructions as load_news_sentiment_skill

SYSTEM_PROMPT = (
    "You are a stock research assistant. You have access to tools for fetching "
    "real stock data and, when genuinely useful, searching the web. Use them to "
    "answer the user's question about a specific ticker. Be concise and factual."
)

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_stock_data",
            "description": "Fetch the current price and basic fundamentals for a stock ticker in a specific market.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"},
                    "market": {"type": "string", "enum": ["US", "India"], "description": "Which market to look up the ticker in"},
                },
                "required": ["ticker", "market"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for recent news about a company. Returns titles, snippets, and URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query, e.g. 'AAPL controversy 2026'"},
                    "max_results": {"type": "integer", "description": "How many results to return"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assess_news_sentiment",
            "description": "Load guidance for judging whether recent news about a company is a genuine cause for investor concern, distinguishing real red flags from routine negative coverage. Call this before forming a final judgment about news-driven risk, ideally after searching for recent news.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

TOOL_REGISTRY = {
    "fetch_stock_data": fetch_stock_data,
    "search_web": search_via_mcp,
    "assess_news_sentiment": load_news_sentiment_skill,
}


async def run_agent(ticker: str, market: str) -> dict:
    # Deliberately narrow for now -- "and outlook" is what was pulling the model
    # toward search_web/assess_news_sentiment. Widening this back out is a
    # prompt change to make once we're deploying, not something to tune blind
    # against local Ollama runs. search_web/assess_news_sentiment stay in
    # TOOL_SCHEMAS either way -- still genuinely available, just rarely the
    # right call for a question this narrow.
    user_message = f"What's the current price of {ticker} in the {market} market?"
    return await _run_agent(SYSTEM_PROMPT, user_message, TOOL_SCHEMAS, TOOL_REGISTRY)


if __name__ == "__main__":
    import asyncio
    print(asyncio.run(run_agent("AAPL", "US")))
