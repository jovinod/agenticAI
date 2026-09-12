import os

from azure.identity import DefaultAzureCredential
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:devpassword@localhost:5433/alpha"
)
DATABASE_HOST = os.environ.get("DATABASE_HOST")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "alpha")
DATABASE_USER = os.environ.get("DATABASE_USER", "")
PG_TOKEN_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"


def _checkpoint_conn_string() -> str:
    """AsyncPostgresSaver speaks psycopg's own conn-string format, not
    SQLAlchemy's dialect-qualified URL, and holds one connection for the
    saver's lifetime rather than opening a fresh one per use the way
    db.py's engine does. An Entra token embedded here is fetched once at
    startup, not refreshed -- a known, real limitation: a worker process
    long-lived enough to outlast the token's validity window would need
    this connection recycled, which this integration does not do.
    """
    if DATABASE_HOST:
        token = DefaultAzureCredential().get_token(PG_TOKEN_SCOPE).token
        return (
            f"postgresql://{DATABASE_USER}:{token}@{DATABASE_HOST}:5432/"
            f"{DATABASE_NAME}?sslmode=require"
        )
    return DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")


_checkpointer = None
_checkpointer_cm = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """One real AsyncPostgresSaver for the worker process's lifetime.
    Entered once and never exited -- the worker runs until the process
    itself stops, same as its Service Bus receiver and database engine."""
    global _checkpointer, _checkpointer_cm
    if _checkpointer is None:
        _checkpointer_cm = AsyncPostgresSaver.from_conn_string(_checkpoint_conn_string())
        _checkpointer = await _checkpointer_cm.__aenter__()
        await _checkpointer.setup()
    return _checkpointer
