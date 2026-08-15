"""
Full loop, isolated: model decides to call a tool -> we actually execute it ->
we feed the real result back -> model produces a genuine final answer.
Still not wired into the worker — proving the mechanism first.
"""
import json
import requests
from tools.stock_data import fetch_stock_data

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

# Name -> real function. The model only ever gives us a STRING name back;
# this table is what turns that string into an actual callable. Nothing below
# is allowed to name a specific function directly -- only this dict decides.
TOOL_REGISTRY = {
    "fetch_stock_data": fetch_stock_data,
}

messages = [{"role": "user", "content": "What's the current price of Apple stock?"}]

print("=" * 70)
print("TURN 1 REQUEST -- sent to the model")
print("=" * 70)
print(json.dumps({"model": "qwen3:8b", "messages": messages, "tools": [TOOL_SCHEMA]}, indent=2))

# --- Turn 1: let the model decide whether/what to call ---
response = requests.post(
    "http://localhost:11434/api/chat",
    json={"model": "qwen3:8b", "messages": messages, "tools": [TOOL_SCHEMA], "stream": False},
)
assistant_message = response.json()["message"]
messages.append(assistant_message)  # its tool-call request becomes part of the ongoing history

print("\n" + "=" * 70)
print("TURN 1 RESPONSE -- raw message from the model")
print("=" * 70)
print(json.dumps(assistant_message, indent=2))

tool_call = assistant_message["tool_calls"][0]
function_name = tool_call["function"]["name"]
function_args = tool_call["function"]["arguments"]
print(f"\nModel wants to call: {function_name}({function_args})")

# --- Dynamic dispatch: look up the function BY THE NAME THE MODEL RETURNED ---
if function_name not in TOOL_REGISTRY:
    raise ValueError(f"Model requested a tool we don't have: {function_name}")

tool_function = TOOL_REGISTRY[function_name]
real_result = tool_function(**function_args)
print(f"Real result from {function_name}: {real_result}")

# --- Feed the real result back, referencing which tool_call it answers ---
messages.append({
    "role": "tool",
    "tool_call_id": tool_call["id"],
    "content": json.dumps(real_result),
})

print("\n" + "=" * 70)
print("TURN 2 REQUEST -- messages array now includes the real tool result")
print("=" * 70)
print(json.dumps(messages, indent=2))

# --- Turn 2: model now has real data, asked to produce the actual answer ---
response2 = requests.post(
    "http://localhost:11434/api/chat",
    json={"model": "qwen3:8b", "messages": messages, "tools": [TOOL_SCHEMA], "stream": False},
)
final_message = response2.json()["message"]

print("\n" + "=" * 70)
print("TURN 2 RESPONSE -- raw final message from the model")
print("=" * 70)
print(json.dumps(final_message, indent=2))

print("\n" + "=" * 70)
print("FINAL ANSWER")
print("=" * 70)
print(final_message["content"])
