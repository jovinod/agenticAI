"""
Isolation test for llm/model_client.py -- confirms the extracted chat()
function behaves identically to the raw requests.post() calls used directly
in test_tool_loop.py, now that it's been pulled out into its own module.
"""
from llm.model_client import chat

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "fetch_stock_data",
        "description": "Fetch the current price and basic fundamentals for a stock ticker in a specific market.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"},
                "market": {"type": "string", "enum": ["US", "India"], "description": "Which market to look up the ticker in"},
            },
            "required": ["ticker", "market"],
        },
    },
}

messages = [{"role": "user", "content": "What's the current price of Apple stock?"}]
result = chat(messages, [TOOL_SCHEMA])

print("Message returned by chat():")
print(result["message"])
print("\nUsage returned by chat():")
print(result["usage"])

assert result["message"]["role"] == "assistant"
assert result["message"]["tool_calls"][0]["function"]["name"] == "fetch_stock_data"
assert result["usage"]["prompt_tokens"] > 0
assert result["usage"]["estimated_cost_usd"] >= 0
print("\nAll checks passed.")
