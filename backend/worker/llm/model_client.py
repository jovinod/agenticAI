"""
Thin wrapper around whichever model backend is actually answering right now.
Everything else in the agent talks to `chat()` and only `chat()` -- this is
the one file that changed to swap Ollama for Azure AI Foundry. agent.py,
context_assembler.py, and every tool are completely untouched by this swap.

Azure's response shape isn't identical to Ollama's -- normalized below so the
rest of the codebase never has to know which backend is actually behind this.
"""
import json
import os
import requests
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


def chat(messages: list[dict], tools: list[dict]) -> dict:
    """Send messages + tool schemas to the model. Returns {"message": ...,
    "usage": {...}} -- message in the SAME shape Ollama returned it
    (tool_calls[i]['function']['arguments'] as a real dict, since that's what
    agent.py's `**function_args` expects); usage carries real token counts
    plus an estimated cost, computed here since this is the one file that
    actually knows which model/deployment answered."""
    response = requests.post(
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
