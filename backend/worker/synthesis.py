from typing import Any, Awaitable, Callable

ChatFunction = Callable[[list[dict], list[dict]], Awaitable[dict]]


async def run_synthesis(
    chat: ChatFunction, system_prompt: str, user_message: str
) -> dict[str, Any]:
    """The direct-call path: data acquisition already happened in
    deterministic application code, so this is one model call with no
    tool schemas -- there is no capability left for the model to choose.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    result = await chat(messages, [])
    return {
        "status": "success",
        "answer": result["message"]["content"],
        "usage": result.get("usage", {}),
    }
