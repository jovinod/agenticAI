"""
Short-term memory -- what's happening in THIS job right now, ephemeral,
cleared shortly after. Distinct from the existing per-ticker Redis cache
(research:{market}:{ticker}:{date}, TTL to midnight): that's a RESULT cache,
only written once a ticker's whole graph run finishes. This is written
DURING a run, one entry per agent as it completes, so a still-running job
has real partial progress to show, not just silence until it's done.

Keyed by (job_id, ticker) -- one multi-ticker request fans out into several
independent graph runs (one per ticker, see worker.py's process_ticker),
each with its own five agents finishing at their own pace.
"""
import os
import redis.asyncio as redis

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6380"))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")
REDIS_SSL = os.environ.get("REDIS_SSL", "false").lower() == "true"

# Short and self-cleaning on purpose -- long enough to cover a real run with
# margin, short enough that this never becomes a second, stale result cache.
PROGRESS_TTL_SECONDS = 600

_redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    ssl=REDIS_SSL,
    decode_responses=True,
)


def _key(job_id: str, ticker: str, agent_name: str) -> str:
    return f"progress:{job_id}:{ticker}:{agent_name}"


async def write_progress(job_id: str, ticker: str, agent_name: str, summary: str) -> None:
    await _redis_client.set(_key(job_id, ticker, agent_name), summary, ex=PROGRESS_TTL_SECONDS)


async def read_progress(job_id: str, ticker: str) -> dict:
    """Returns {agent_name: summary} for whichever agents have finished so
    far -- agents that haven't completed yet just aren't in the dict."""
    progress = {}
    for agent_name in ("fundamentals", "technical", "news", "risk", "synthesizer"):
        value = await _redis_client.get(_key(job_id, ticker, agent_name))
        if value is not None:
            progress[agent_name] = value
    return progress
