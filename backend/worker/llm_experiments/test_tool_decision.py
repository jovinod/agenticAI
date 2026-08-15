"""
Isolation test — does the model correctly DECIDE to call a tool, with sensible
arguments, given only its schema? Not yet executing anything real; that's the
next piece. Same "prove the mechanism standalone first" discipline as arq/MCP.
"""
import json
import requests

# Same shape as fetch_stock_data(ticker, market) — described to the model,
# not actually wired to the real function yet.
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

response = requests.post(
    "http://localhost:11434/api/chat",
    json={
        "model": "qwen3:8b",
        "messages": [{"role": "user", "content": "What's the current price of Apple stock?"}],
        "tools": [TOOL_SCHEMA],
        "stream": False,
    },
)

result = response.json()
print("Full response message:")
print(json.dumps(result["message"], indent=2))
