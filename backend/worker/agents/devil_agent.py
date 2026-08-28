"""
Devil's Advocate agent -- genuine adversarial verification, not aggregation.
Unlike Decision (which weighs signals toward a verdict) or News (which
explores for new information), this agent's only job is to try to break
whatever the other four agents already concluded: search for counter-evidence
to their SPECIFIC claims, judge whether what it finds actually contradicts
something or is just noise, and decide whether to refine its search or
conclude -- genuine multi-turn judgment, adversarial rather than exploratory.

Read-only by design (see book/chapter-08-auth.md, Section F.4): the only
tool in this registry is search_web. There is no write path here at all,
which makes this the cleanest example in this project of a tool registry
enforcing a role rather than just a capability -- an agent whose entire
purpose is finding problems has no way to fix or touch anything itself.

Adapted from buynobuy's real devil_agent.py / skills/devil/devil_analyser.py,
with one deliberate change: that version runs a fixed set of generic bearish
queries and makes a single LLM call. This one searches for counter-evidence
to the SPECIFIC claims already made in this run, and can choose to search
again with a sharper query -- a real loop, not a two-step pipeline.
"""
from agent_harness import run_agent
from tools.web_search import search_via_mcp
from llm.parse_json import parse_llm_json

SYSTEM_PROMPT = (
    "You are a ruthlessly skeptical short-seller building the sharpest, most honest "
    "counter-thesis against a stock -- not a balanced view, the strongest case AGAINST "
    "buying it. You will be given the other analysts' fundamentals, technical, news, and "
    "risk assessments. Search the web for counter-evidence to their SPECIFIC claims -- "
    "not generic bad news, evidence that directly undermines what they said. "
    "Search AT MOST twice, total -- pick the single most promising angle first; only "
    "search a second time if that first search came back genuinely empty, and then stop "
    "and conclude with whatever you have. Do not invent numbers or claims not present in "
    "the search results or the other analysts' assessments. "
    "Respond with ONLY a JSON object: "
    '{"bear_score": <1-10, 1=extremely bearish, 10=no real concerns>, '
    '"summary": "<1 sentence: the real structural risk, not just \\"the business is bad\\">", '
    '"reasons": [{"heading": "<5-8 words>", "detail": "<2-3 sentences, specific>"}], '
    '"closing_fact": "<1-2 sentences: the single most uncomfortable structural truth>", '
    '"confidence": "high|medium|low"}'
)


async def run(ticker: str, market: str, fundamentals_summary: str, technical_summary: str, news_summary: str, risk_summary: str) -> dict:
    tool_schemas = [
        {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the web for counter-evidence to a specific claim about this company.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "A targeted search query, e.g. 'AAPL antitrust ruling 2026 impact'"},
                        "max_results": {"type": "integer", "description": "How many results to return"},
                    },
                    "required": ["query"],
                },
            },
        },
    ]
    tool_registry = {"search_web": search_via_mcp}

    user_message = (
        f"Ticker: {ticker} ({market} market)\n\n"
        f"Fundamentals: {fundamentals_summary}\n\n"
        f"Technical: {technical_summary}\n\n"
        f"News: {news_summary}\n\n"
        f"Risk: {risk_summary}\n\n"
        "Build the bear case against this stock."
    )

    result = await run_agent(SYSTEM_PROMPT, user_message, tool_schemas, tool_registry)

    parsed, parse_err = parse_llm_json(result.get("answer", "")) if result.get("status") == "success" else ({}, "loop did not conclude")
    if parse_err:
        parsed = {
            "bear_score": None, "summary": f"Devil's Advocate synthesis failed: {parse_err}",
            "reasons": [], "closing_fact": "", "confidence": "low",
        }

    parsed["usage"] = result.get("usage", {})
    parsed["answer"] = parsed.get("summary", "")
    return parsed
