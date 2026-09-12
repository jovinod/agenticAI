import inspect
import json
from typing import Any, Awaitable, Callable

from context_assembler import assemble_context

# An async or sync callable: (messages, tool_schemas) -> {"message": {...}, "usage": {...}}.
# Provider-specific transport is deliberately not wired in here -- Chapter
# 7 normalizes that behind one client. Tests supply a fake, scripted chat.
ChatFunction = Callable[[list[dict], list[dict]], Awaitable[dict]]


def _merge_usage(total: dict[str, int], usage: dict[str, int]) -> dict[str, int]:
    merged = dict(total)
    for key, value in usage.items():
        merged[key] = merged.get(key, 0) + value
    return merged


async def _call_tool(
    function_name: str,
    function_args: dict[str, Any],
    tool_registry: dict[str, Callable],
) -> Any:
    """The application-owned dispatcher. An allowlist, not a lookup table
    for arbitrary code: a name absent from the registry never executes."""
    if function_name not in tool_registry:
        return {"error": f"unknown tool: {function_name}"}

    function = tool_registry[function_name]
    result = function(**function_args)
    if inspect.isawaitable(result):
        result = await result
    return result


async def run_agent(
    chat: ChatFunction,
    system_prompt: str,
    user_message: str,
    tool_schemas: list[dict],
    tool_registry: dict[str, Callable],
    max_turns: int = 5,
) -> dict[str, Any]:
    """The budgeted state machine: model proposes, harness mediates.

    Terminates with `success` once the model returns content without a
    tool call, or with `max_turns_exceeded` once the turn budget runs
    out -- the two outcomes are never allowed to look alike.
    """
    history: list[dict] = [{"role": "user", "content": user_message}]
    total_usage: dict[str, int] = {}
    partial_results: list[Any] = []

    for _ in range(max_turns):
        messages = assemble_context(history, system_prompt)
        result = await chat(messages, tool_schemas)
        response = result["message"]
        total_usage = _merge_usage(total_usage, result.get("usage", {}))
        history.append(response)

        tool_calls = response.get("tool_calls")
        if not tool_calls:
            return {
                "status": "success",
                "answer": response["content"],
                "usage": total_usage,
            }

        for tool_call in tool_calls:
            tool_result = await _call_tool(
                tool_call["function"]["name"],
                tool_call["function"]["arguments"],
                tool_registry,
            )
            partial_results.append(tool_result)
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(tool_result),
                }
            )

    return {
        "status": "max_turns_exceeded",
        "partial_results": partial_results,
        "usage": total_usage,
    }
