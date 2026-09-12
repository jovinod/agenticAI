from typing import Any


def build_thread_id(job_id: str, ticker: str) -> str:
    """One API job can fan out into several ticker messages. job_id
    alone would mix independent graph histories, so thread identity is
    the pair."""
    return f"{job_id}:{ticker}"


async def resolve_resume_input(
    checkpointer, thread_id: str, initial_state: dict
) -> tuple[dict | None, dict]:
    """A fresh thread must receive initial state. An existing thread
    must receive None so LangGraph resumes rather than treating
    repeated input as a new update -- calling None for a never-seen
    thread produces no starting state."""
    config = {"configurable": {"thread_id": thread_id}}
    existing = await checkpointer.aget_tuple(config)
    resume_input = None if existing else initial_state
    return resume_input, config
