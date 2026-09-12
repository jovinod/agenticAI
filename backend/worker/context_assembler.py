def assemble_context(history: list[dict], system_prompt: str) -> list[dict]:
    """One owner for what is sent on each model call.

    Prepends the system prompt and strips stale provider-specific
    `thinking` fields while preserving user, assistant, tool-call, and
    tool-result messages. Context-window trimming would belong here too,
    once histories are large enough to need it.
    """
    messages = [{"role": "system", "content": system_prompt}]

    for message in history:
        if message["role"] == "assistant" and "thinking" in message:
            message = {key: value for key, value in message.items() if key != "thinking"}
        messages.append(message)

    return messages
