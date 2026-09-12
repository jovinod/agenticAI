import os

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:devpassword@localhost:5433/alpha"
)
# AsyncPostgresSaver speaks psycopg's own conn-string format, not
# SQLAlchemy's dialect-qualified URL.
_CHECKPOINT_CONN_STRING = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

_checkpointer = None
_checkpointer_cm = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """One real AsyncPostgresSaver for the worker process's lifetime.
    Entered once and never exited -- the worker runs until the process
    itself stops, same as its Service Bus receiver and database engine."""
    global _checkpointer, _checkpointer_cm
    if _checkpointer is None:
        _checkpointer_cm = AsyncPostgresSaver.from_conn_string(_CHECKPOINT_CONN_STRING)
        _checkpointer = await _checkpointer_cm.__aenter__()
        await _checkpointer.setup()
    return _checkpointer
