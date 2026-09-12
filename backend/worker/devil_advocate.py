import inspect
from typing import Any, Awaitable, Callable

SEARCH_WEB_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search for evidence that contradicts a specific claim already made.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    },
}


def build_registry(search_web: Callable) -> dict[str, Callable]:
    """The dissent registry contains only search. The harness cannot
    dispatch a database write, queue operation, or recommendation
    change, because none is registered here -- a real capability
    boundary inside the process, even though the worker as a whole
    still holds broader credentials for its own responsibilities."""
    return {"search_web": search_web}


async def dispatch(
    function_name: str,
    function_args: dict[str, Any],
    tool_registry: dict[str, Callable],
) -> Any:
    if function_name not in tool_registry:
        return {"error": f"unknown tool: {function_name}"}

    function = tool_registry[function_name]
    result = function(**function_args)
    if inspect.isawaitable(result):
        result = await result
    return result


ChatFunction = Callable[[list[dict], list[dict]], Awaitable[dict]]


async def run_devil_advocate(
    chat: ChatFunction,
    summaries: dict[str, str],
    search_web: Callable,
    max_turns: int = 3,
) -> dict[str, Any]:
    """Receives the existing summaries and searches for evidence that
    contradicts their concrete claims. A malformed response is parsed
    into a low-confidence fallback rather than copied into state as if
    it were valid structured dissent."""
    tool_registry = build_registry(search_web)
    system_prompt = (
        "You are a devil's advocate. Search for evidence that contradicts "
        "the claims below. Use no more than two searches."
    )
    user_message = "\n".join(f"{name}: {summary}" for name, summary in summaries.items())
    history: list[dict] = [{"role": "user", "content": user_message}]

    for _ in range(max_turns):
        messages = [{"role": "system", "content": system_prompt}, *history]
        result = await chat(messages, [SEARCH_WEB_SCHEMA])
        response = result["message"]
        history.append(response)

        tool_calls = response.get("tool_calls")
        if not tool_calls:
            content = response.get("content")
            if not content:
                return {"dissent": "No counter-evidence found.", "confidence": "low"}
            return {"dissent": content, "confidence": "normal"}

        for tool_call in tool_calls:
            tool_result = await dispatch(
                tool_call["function"]["name"],
                tool_call["function"]["arguments"],
                tool_registry,
            )
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": str(tool_result),
                }
            )

    return {"dissent": "No conclusion reached within the turn budget.", "confidence": "low"}
