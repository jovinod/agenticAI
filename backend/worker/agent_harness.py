"""
The reusable agent harness -- the loop + dispatcher that any single agent
runs on, regardless of which one it is. Wires together everything proven
separately in Phase 4: the Context Assembler, the model client, and a
name->function tool registry (same dispatch pattern proven in
llm_experiments/test_tool_loop.py, generalized into a real bounded loop).

Phase 5 split this out of what used to be agent.py: that file was hardcoded
to one system prompt and one fixed toolset -- fine for a single agent, wrong
the moment there are five. Each agent (backend/worker/agents/*.py) now
brings its OWN system prompt, tool schemas, and tool registry, and calls
run_agent() here -- the same harness cycle, run once per agent, exactly the
Harness-vs-Orchestrator shape from book/chapter-04-the-first-agent.md made
concrete: the orchestrator (Phase 5's LangGraph graph) decides which agent
runs when; each agent still goes through this one shared harness.
"""
import inspect
import json
from context_assembler import assemble_context
from llm.model_client import chat

# A hard cap on how many turns the loop can take before giving up -- without
# this, a confused or looping model could call tools indefinitely, burning
# time and (once a real paid model is behind this) real money with no result.
DEFAULT_MAX_TURNS = 5


async def _call_tool(function_name: str, function_args: dict, tool_registry: dict):
    if function_name not in tool_registry:
        return {"error": f"unknown tool: {function_name}"}

    tool_function = tool_registry[function_name]
    if inspect.iscoroutinefunction(tool_function):
        return await tool_function(**function_args)
    return tool_function(**function_args)


def _accumulate(total: dict, usage: dict) -> None:
    for key in total:
        total[key] += usage[key]


async def run_agent(
    system_prompt: str,
    user_message: str,
    tool_schemas: list[dict],
    tool_registry: dict,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> dict:
    """
    Returns a typed result -- never a bare string -- so a caller can tell a
    real answer apart from a give-up. {"status": "success", "answer": ...} on
    a real final answer; {"status": "max_turns_exceeded", "partial_results": [...]}
    if the loop ran out of turns first, carrying back whatever real tool
    results were actually gathered rather than nothing at all. Either way,
    "usage" carries the REAL token/cost total across every turn -- a run that
    calls the model three times before answering costs three calls' worth,
    not just the last one.
    """
    history = [{"role": "user", "content": user_message}]
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0}

    for _ in range(max_turns):
        messages = assemble_context(history, system_prompt)
        result = await chat(messages, tool_schemas)
        response = result["message"]
        _accumulate(total_usage, result["usage"])
        history.append(response)

        tool_calls = response.get("tool_calls")
        if not tool_calls:
            return {"status": "success", "answer": response["content"], "usage": total_usage}

        # A single response can request more than one tool call -- each one
        # needs its own result, tagged back with its own tool_call_id.
        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]
            function_args = tool_call["function"]["arguments"]
            print(f"-> calling {function_name}({function_args})")
            tool_result = await _call_tool(function_name, function_args, tool_registry)

            history.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": json.dumps(tool_result),
            })

    return {
        "status": "max_turns_exceeded",
        "partial_results": [json.loads(m["content"]) for m in history if m["role"] == "tool"],
        "usage": total_usage,
    }


async def run_synthesis(system_prompt: str, user_message: str) -> dict:
    """
    A single LLM call, no tools, no loop -- for agents where fetching is a
    direct call (no genuine choice involved, see tools/stock_data.py's own
    docstring) and the model's only job is synthesizing already-gathered data
    into a narrative. Cheaper than run_agent's loop, and avoids paying
    tool-schema token overhead for a call that was never going to use any
    tools anyway -- confirmed as a real, deliberate buynobuy pattern too, not
    just a guess: "avoids LangGraph tool-schema overhead (~8K tokens saved
    per call)."
    """
    messages = assemble_context([{"role": "user", "content": user_message}], system_prompt)
    result = await chat(messages, tools=[])
    return {"status": "success", "answer": result["message"]["content"], "usage": result["usage"]}
