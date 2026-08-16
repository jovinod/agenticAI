"""
The real single-agent function -- given a ticker and market, decides which
tool(s) to call, gets real data, and produces a genuine summary. Wires
together everything proven separately so far: the Context Assembler, the
model client, and a name->function tool registry (same dispatch pattern
proven in llm_experiments/test_tool_loop.py, now generalized into a real
loop instead of a fixed two-turn script).

Async since search_web (the MCP-backed tool) is a real coroutine -- this
also means run_agent is now shaped correctly to be called from worker.py's
own async loop once it's wired in for real.
"""
import inspect
import json
from context_assembler import assemble_context
from llm.model_client import chat
from tools.stock_data import fetch_stock_data
from tools.web_search import search_via_mcp
from skills.assess_news_sentiment.skill import load_instructions as load_news_sentiment_skill

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
            # This description is the whole discovery mechanism -- the model reads it
            # among its available tools and decides for itself whether it's relevant,
            # exactly the way it decides whether fetch_stock_data is relevant.
            "description": "Load guidance for judging whether recent news about a company is a genuine cause for investor concern, distinguishing real red flags from routine negative coverage. Call this before forming a final judgment about news-driven risk, ideally after searching for recent news.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

TOOL_REGISTRY = {
    "fetch_stock_data": fetch_stock_data,
    "search_web": search_via_mcp,
    # Calling this "tool" doesn't compute anything -- it just returns instructions
    # for the MODEL to apply with its own judgment on the next turn. That's the
    # actual difference between a Skill and a plain tool in this codebase.
    # Note the string key ("assess_news_sentiment", matching the schema's "name" --
    # this is the tool's identity to the model) is deliberately NOT the same as the
    # Python function name (load_news_sentiment_skill, describing what it actually
    # does) -- collapsing those two would make it look like this function performs
    # the assessment itself, when really it only loads instructions for one.
    "assess_news_sentiment": load_news_sentiment_skill,
}

# A hard cap on how many turns the loop can take before giving up -- without
# this, a confused or looping model could call tools indefinitely, burning
# time and (once a real paid model is behind this) real money with no result.
MAX_TURNS = 5


async def _call_tool(function_name: str, function_args: dict):
    if function_name not in TOOL_REGISTRY:
        return {"error": f"unknown tool: {function_name}"}

    tool_function = TOOL_REGISTRY[function_name]
    if inspect.iscoroutinefunction(tool_function):
        return await tool_function(**function_args)
    return tool_function(**function_args)


async def run_agent(ticker: str, market: str) -> dict:
    """
    Returns a typed result -- never a bare string -- so a caller can tell a
    real answer apart from a give-up. {"status": "success", "answer": ...} on
    a real final answer; {"status": "max_turns_exceeded", "partial_results": [...]}
    if the loop ran out of turns first, carrying back whatever real tool
    results were actually gathered rather than nothing at all.
    """
    # Deliberately narrow for now -- "and outlook" is what was pulling the model
    # toward search_web/assess_news_sentiment. Widening this back out is a
    # prompt change to make once we're deploying, not something to tune blind
    # against local Ollama runs. search_web/assess_news_sentiment stay in
    # TOOL_SCHEMAS either way -- still genuinely available, just rarely the
    # right call for a question this narrow.
    history = [
        {"role": "user", "content": f"What's the current price of {ticker} in the {market} market?"}
    ]

    for _ in range(MAX_TURNS):
        messages = assemble_context(history)
        response = chat(messages, TOOL_SCHEMAS)
        history.append(response)

        tool_calls = response.get("tool_calls")
        if not tool_calls:
            return {"status": "success", "answer": response["content"]}

        # A single response can request more than one tool call -- each one
        # needs its own result, tagged back with its own tool_call_id.
        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]
            function_args = tool_call["function"]["arguments"]
            print(f"-> calling {function_name}({function_args})")
            result = await _call_tool(function_name, function_args)

            history.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": json.dumps(result),
            })

    return {
        "status": "max_turns_exceeded",
        "partial_results": [json.loads(m["content"]) for m in history if m["role"] == "tool"],
    }


if __name__ == "__main__":
    import asyncio
    print(asyncio.run(run_agent("AAPL", "US")))
