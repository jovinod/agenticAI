from typing import TypedDict

import httpx
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy


class RetryState(TypedDict, total=False):
    result: str


def build_isolated_retry_graph(call_counts: dict[str, int]):
    """A node with NO in-node catch. This proves LangGraph's own retry
    policy can retry an escaping exception -- it does not prove the
    application's agent nodes expose their failures to that policy."""

    async def flaky_node(state: RetryState) -> dict:
        call_counts["flaky"] = call_counts.get("flaky", 0) + 1
        if call_counts["flaky"] == 1:
            raise httpx.ReadError("simulated transient network failure")
        return {"result": "recovered"}

    builder = StateGraph(RetryState)
    builder.add_node("flaky", flaky_node, retry_policy=RetryPolicy(initial_interval=0.01))
    builder.add_edge(START, "flaky")
    builder.add_edge("flaky", END)

    return builder.compile()
