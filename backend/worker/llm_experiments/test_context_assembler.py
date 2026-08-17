"""
Isolation test for context_assembler.py -- no model call, no network. Just
confirms the stripping/system-prompt logic does what it claims on a fake
history, same "prove the small piece alone first" discipline used everywhere
else in this project.
"""
import json
from context_assembler import assemble_context

fake_history = [
    {"role": "user", "content": "What's the current price of Apple stock?"},
    {
        "role": "assistant",
        "content": "",
        "thinking": "The user wants Apple's price... I should call fetch_stock_data.",
        "tool_calls": [{"id": "call_1", "function": {"name": "fetch_stock_data", "arguments": {"ticker": "AAPL", "market": "US"}}}],
    },
    {"role": "tool", "tool_call_id": "call_1", "content": json.dumps({"price": 305.93})},
]

result = assemble_context(fake_history, system_prompt="You are a stock research assistant.")

print(json.dumps(result, indent=2))

assert result[0] == {"role": "system", "content": "You are a stock research assistant."}, "system prompt should be first"
assert "thinking" not in result[2], "thinking should be stripped from the assistant message"
assert result[2]["tool_calls"] == fake_history[1]["tool_calls"], "tool_calls should survive stripping"
assert result[1] == fake_history[0], "plain user message should pass through unchanged"
assert result[3] == fake_history[2], "tool result message should pass through unchanged"

print("\nAll checks passed.")
