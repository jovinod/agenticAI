"""
Context Assembler -- the one place responsible for deciding exactly what goes
into the `messages` array sent to the model on every call. Nothing else in the
agent should build that array by hand (see llm_experiments/test_tool_loop.py
for what doing it inline, unexamined, looked like before this existed).
"""

SYSTEM_PROMPT = (
    "You are a stock research assistant. You have access to tools for fetching "
    "real stock data and, when genuinely useful, searching the web. Use them to "
    "answer the user's question about a specific ticker. Be concise and factual."
)


def assemble_context(history: list[dict]) -> list[dict]:
    """
    Takes the conversation so far (the running list of user/assistant/tool
    messages built up over the loop) and returns exactly what should be sent
    to the model on the NEXT call: a system prompt, plus the history with any
    stale assistant "thinking" (scratchpad) content stripped out.

    Trimming-to-fit-context-window would also live here -- not implemented
    yet, since nothing this project sends today is remotely close to a real
    context window limit. Named as a placeholder so the responsibility has an
    obvious home when it's actually needed, not bolted on as an afterthought.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for message in history:
        if message["role"] == "assistant" and "thinking" in message:
            message = {k: v for k, v in message.items() if k != "thinking"}
        messages.append(message)

    return messages
