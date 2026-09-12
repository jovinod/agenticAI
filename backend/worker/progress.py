import os

from redis import asyncio as redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

# Ten minutes: long enough to expose completed stages during a normal
# run, short enough that progress never becomes a second report database.
PROGRESS_TTL_SECONDS = 600

redis_client = redis.from_url(REDIS_URL)


def _key(job_id: str, ticker: str, agent_name: str) -> str:
    return f"progress:{job_id}:{ticker}:{agent_name}"


async def write_progress(job_id: str, ticker: str, agent_name: str, summary: str) -> None:
    """A graph node writes only after it has a result. An absent key
    means "not completed," not an empty answer."""
    await redis_client.set(
        _key(job_id, ticker, agent_name),
        summary,
        ex=PROGRESS_TTL_SECONDS,
    )


async def read_progress(job_id: str, ticker: str, agent_names: list[str]) -> dict[str, str]:
    """Returns only the agents that have actually completed."""
    completed = {}
    for agent_name in agent_names:
        value = await redis_client.get(_key(job_id, ticker, agent_name))
        if value is not None:
            completed[agent_name] = value.decode() if isinstance(value, bytes) else value
    return completed
