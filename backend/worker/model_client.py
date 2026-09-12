import json
import os
from typing import Any

import httpx

APIM_BASE_URL = os.environ.get("APIM_BASE_URL", "")
APIM_SUBSCRIPTION_KEY = os.environ.get("APIM_SUBSCRIPTION_KEY", "")
API_VERSION = os.environ.get("APIM_API_VERSION", "2024-10-21")
CHAT_URL = f"{APIM_BASE_URL}/openai/deployments/chat/chat/completions"

# Placeholders: real prices depend on the exact deployment, region,
# pricing unit, and cached-token rules -- provider token counts are
# evidence, the dollar conversion is application policy.
PRICE_PER_1K_PROMPT_TOKENS = 0.0
PRICE_PER_1K_COMPLETION_TOKENS = 0.0


def _stringify_tool_call_args(messages: list[dict]) -> list[dict]:
    """Azure's chat API expects tool-call arguments as JSON strings; the
    harness dispatches from dictionaries. Converting an outbound copy
    keeps the transcript the harness continues to extend untouched."""
    prepared = []
    for message in messages:
        if message.get("tool_calls"):
            message = {
                **message,
                "tool_calls": [
                    {
                        **call,
                        "function": {
                            **call["function"],
                            "arguments": json.dumps(call["function"]["arguments"]),
                        },
                    }
                    for call in message["tool_calls"]
                ],
            }
        prepared.append(message)
    return prepared


def _parse_tool_call_args(message: dict) -> dict:
    """The reverse conversion: callers see one canonical dictionary form
    in both old and new transcript entries."""
    if not message.get("tool_calls"):
        return message
    return {
        **message,
        "tool_calls": [
            {
                **call,
                "function": {
                    **call["function"],
                    "arguments": json.loads(call["function"]["arguments"])
                    if isinstance(call["function"]["arguments"], str)
                    else call["function"]["arguments"],
                },
            }
            for call in message["tool_calls"]
        ],
    }


def _normalize_usage(raw_usage: dict[str, Any]) -> dict[str, Any]:
    prompt_tokens = raw_usage.get("prompt_tokens", 0)
    completion_tokens = raw_usage.get("completion_tokens", 0)
    estimated_cost_usd = (
        prompt_tokens / 1000 * PRICE_PER_1K_PROMPT_TOKENS
        + completion_tokens / 1000 * PRICE_PER_1K_COMPLETION_TOKENS
    )
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": raw_usage.get("total_tokens", prompt_tokens + completion_tokens),
        "estimated_cost_usd": estimated_cost_usd,
    }


async def chat(messages: list[dict], tools: list[dict]) -> dict:
    """The harness's one stable model operation. Callers never see a
    provider SDK response class -- only this normalized shape."""
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            CHAT_URL,
            params={"api-version": API_VERSION},
            headers={
                "Ocp-Apim-Subscription-Key": APIM_SUBSCRIPTION_KEY,
                "Content-Type": "application/json",
            },
            json={
                "messages": _stringify_tool_call_args(messages),
                **({"tools": tools} if tools else {}),
            },
        )
        response.raise_for_status()
        body = response.json()

    raw_message = body["choices"][0]["message"]
    return {
        "message": _parse_tool_call_args(raw_message),
        "usage": _normalize_usage(body.get("usage", {})),
    }
