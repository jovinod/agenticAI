"""
News agent -- unlike fundamentals/technical, there's genuine judgment here:
what to search for, and whether the sentiment skill applies to what's found.
Keeps the full tool-calling loop from Phase 4, just as its own dedicated
agent now instead of one option among several in a single flat agent.
"""
from agent_harness import run_agent
from tools.web_search import search_via_mcp
from skills.assess_news_sentiment.skill import load_instructions as load_news_sentiment_skill

SYSTEM_PROMPT = (
    "You are a news research agent. Search the web for recent news about the "
    "given company, then use the assess_news_sentiment tool to judge whether "
    "anything found is a genuine cause for investor concern, as opposed to "
    "routine coverage. Be concise -- 2-3 sentences, and state plainly if "
    "nothing concerning was found."
)

TOOL_SCHEMAS = [
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
    "search_web": search_via_mcp,
    "assess_news_sentiment": load_news_sentiment_skill,
}


async def run(ticker: str, market: str) -> dict:
    user_message = f"Research recent news for {ticker} ({market} market) and assess whether anything is concerning."
    return await run_agent(SYSTEM_PROMPT, user_message, TOOL_SCHEMAS, TOOL_REGISTRY)
