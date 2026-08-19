"""
News agent -- unlike fundamentals/technical, there's genuine judgment here:
what to search for, and whether any discovered skill applies to what's
found. Keeps the full tool-calling loop from Phase 4, just as its own
dedicated agent now instead of one option among several in a single flat
agent.

Skills are no longer hardcoded here by name -- discover_skills() scans
skills/ for whatever's actually there (today: just assess_news_sentiment).
Adding a second discoverable skill later needs zero changes to this file;
that's the actual point of "discovery" over "hardcoding."
"""
from agent_harness import run_agent
from tools.web_search import search_via_mcp
from skills.discovery import discover_skills

SYSTEM_PROMPT = (
    "You are a news research agent. Search the web for recent news about the "
    "given company, then use any relevant skill available to you to judge "
    "whether anything found is a genuine cause for investor concern, as "
    "opposed to routine coverage. Be concise -- 2-3 sentences, and state "
    "plainly if nothing concerning was found."
)

_skill_schemas, _skill_registry = discover_skills()

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
    *_skill_schemas,
]

TOOL_REGISTRY = {
    "search_web": search_via_mcp,
    **_skill_registry,
}


async def run(ticker: str, market: str) -> dict:
    user_message = f"Research recent news for {ticker} ({market} market) and assess whether anything is concerning."
    return await run_agent(SYSTEM_PROMPT, user_message, TOOL_SCHEMAS, TOOL_REGISTRY)
