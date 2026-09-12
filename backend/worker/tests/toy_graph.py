from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class ToyState(TypedDict):
    value: int


def build_toy_graph(checkpointer, calls: dict[str, int], fail_on_first_c: bool = True):
    """A minimal sequential graph making the resume promise testable
    without model calls: node c raises on its first invocation, so a
    resume with the same thread ID must not repeat a and b."""

    def a(state: ToyState) -> dict:
        calls["a"] += 1
        return {"value": state["value"] + 1}

    def b(state: ToyState) -> dict:
        calls["b"] += 1
        return {"value": state["value"] + 1}

    def c(state: ToyState) -> dict:
        calls["c"] += 1
        if fail_on_first_c and calls["c"] == 1:
            raise RuntimeError("simulated crash")
        return {"value": state["value"] + 1}

    builder = StateGraph(ToyState)
    builder.add_node("a", a)
    builder.add_node("b", b)
    builder.add_node("c", c)
    builder.add_edge(START, "a")
    builder.add_edge("a", "b")
    builder.add_edge("b", "c")
    builder.add_edge("c", END)

    return builder.compile(checkpointer=checkpointer)
