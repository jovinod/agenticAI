"""
Thin wrapper around whichever model backend is actually answering right now.
Everything else in the agent talks to `chat()` and only `chat()` -- this is
the one file that changed to swap Ollama for Azure AI Foundry. agent.py,
context_assembler.py, and every tool are completely untouched by this swap.

Azure's response shape isn't identical to Ollama's -- normalized below so the
rest of the codebase never has to know which backend is actually behind this.

Phase 5: was `requests.post()`, a synchronous, blocking call -- meaning
`chat()`, despite every caller being `async def`, silently froze the whole
event loop while waiting for a response. Real, measured consequence: three
"parallel" agent branches in agents/graph.py ran almost fully sequentially
(45s wall-clock, close to the SUM of each agent's own time, not the max).
httpx.AsyncClient actually yields control during the network wait, letting
other coroutines run -- this is what real concurrency in this codebase
depends on, not just wiring parallel edges in a graph.
"""
import json
import os
import httpx
from dotenv import load_dotenv

# No-op in Azure (no .env.local there) -- Container Apps sets real env vars
# directly, same pattern already used in worker.py.
load_dotenv(".env.local")

AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
AZURE_OPENAI_KEY = os.environ["AZURE_OPENAI_KEY"]
AZURE_OPENAI_DEPLOYMENT = os.environ["AZURE_OPENAI_DEPLOYMENT"]
API_VERSION = "2024-08-01-preview"

CHAT_URL = (
    f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}"
    f"/chat/completions?api-version={API_VERSION}"
)

# Placeholder rates -- NOT verified against a live Azure OpenAI pricing page.
# Good enough to prove the logging mechanism actually works end to end; swap
# in this deployment's real current per-1K-token pricing before trusting
# these numbers for any real budgeting decision.
PRICE_PER_1K_PROMPT_TOKENS = 0.00025
PRICE_PER_1K_COMPLETION_TOKENS = 0.001


def _stringify_tool_call_args(messages: list[dict]) -> list[dict]:
    """Azure expects tool_calls[i]['function']['arguments'] as a JSON STRING
    on the way in, even though we keep it as a real dict everywhere else in
    our own code (agent.py's `**function_args` needs a dict). Builds a fresh
    copy for the outgoing request only -- never mutates `messages` itself,
    since that same list is `history`, still being built up turn by turn."""
    prepared = []
    for message in messages:
        if message.get("tool_calls"):
            message = {
                **message,
                "tool_calls": [
                    {**tc, "function": {**tc["function"], "arguments": json.dumps(tc["function"]["arguments"])}}
                    for tc in message["tool_calls"]
                ],
            }
        prepared.append(message)
    return prepared


async def chat(messages: list[dict], tools: list[dict]) -> dict:
    """Send messages + tool schemas to the model. Returns {"message": ...,
    "usage": {...}} -- message in the SAME shape Ollama returned it
    (tool_calls[i]['function']['arguments'] as a real dict, since that's what
    agent.py's `**function_args` expects); usage carries real token counts
    plus an estimated cost, computed here since this is the one file that
    actually knows which model/deployment answered.

    A fresh httpx.AsyncClient per call, not a persistent shared one -- simpler,
    and correct for fixing the concurrency bug this was written to fix. A
    persistent client (reused across calls, same reasoning as the Service Bus
    sender in backend/api/main.py) is a further optimization, not required to
    get real parallel agents working.

    Explicit timeout -- httpx defaults to 5s, far too short for an LLM
    completion (requests, used before, had no default timeout at all, so this
    never came up until switching). Genuinely mattered here: running three
    agents concurrently means they're competing for the same rate-limited
    Azure OpenAI capacity, so responses can legitimately take longer under
    real concurrent load than they did one at a time."""
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            CHAT_URL,
            headers={"api-key": AZURE_OPENAI_KEY, "Content-Type": "application/json"},
            json={"messages": _stringify_tool_call_args(messages), "tools": tools},
        )
    response.raise_for_status()
    body = response.json()
    message = body["choices"][0]["message"]

    if message.get("tool_calls"):
        for tool_call in message["tool_calls"]:
            tool_call["function"]["arguments"] = json.loads(tool_call["function"]["arguments"])

    raw_usage = body.get("usage", {})
    prompt_tokens = raw_usage.get("prompt_tokens", 0)
    completion_tokens = raw_usage.get("completion_tokens", 0)
    estimated_cost_usd = (
        prompt_tokens / 1000 * PRICE_PER_1K_PROMPT_TOKENS
        + completion_tokens / 1000 * PRICE_PER_1K_COMPLETION_TOKENS
    )

    return {
        "message": message,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": raw_usage.get("total_tokens", 0),
            "estimated_cost_usd": round(estimated_cost_usd, 6),
        },
    }
