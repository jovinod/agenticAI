"""
The real single-agent function -- given a ticker and market, decides which
tool(s) to call, gets real data, and produces a genuine summary. Wires
together everything proven separately so far: the Context Assembler, the
model client, and a name->function tool registry (same dispatch pattern
proven in llm_experiments/test_tool_loop.py, now generalized into a real
loop instead of a fixed two-turn script).
"""
import json
from context_assembler import assemble_context
from llm.model_client import chat
from tools.stock_data import fetch_stock_data

TOOL_SCHEMAS = [
    {
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
    },
]

TOOL_REGISTRY = {
    "fetch_stock_data": fetch_stock_data,
}

# A hard cap on how many turns the loop can take before giving up -- without
# this, a confused or looping model could call tools indefinitely, burning
# time and (once a real paid model is behind this) real money with no result.
MAX_TURNS = 5


def run_agent(ticker: str, market: str) -> dict:
    """
    Returns a typed result -- never a bare string -- so a caller can tell a
    real answer apart from a give-up. {"status": "success", "answer": ...} on
    a real final answer; {"status": "max_turns_exceeded", "partial_results": [...]}
    if the loop ran out of turns first, carrying back whatever real tool
    results were actually gathered rather than nothing at all.
    """
    history = [
        {"role": "user", "content": f"What's the current price and outlook for {ticker} in the {market} market?"}
    ]

    for _ in range(MAX_TURNS):
        messages = assemble_context(history)
        response = chat(messages, TOOL_SCHEMAS)
        history.append(response)

        tool_calls = response.get("tool_calls")
        if not tool_calls:
            return {"status": "success", "answer": response["content"]}

        # A single response can request more than one tool call -- each one
        # needs its own result, tagged back with its own tool_call_id.
        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]
            function_args = tool_call["function"]["arguments"]

            if function_name not in TOOL_REGISTRY:
                result = {"error": f"unknown tool: {function_name}"}
            else:
                result = TOOL_REGISTRY[function_name](**function_args)

            history.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": json.dumps(result),
            })

    return {
        "status": "max_turns_exceeded",
        "partial_results": [json.loads(m["content"]) for m in history if m["role"] == "tool"],
    }


if __name__ == "__main__":
    print(run_agent("AAPL", "US"))
