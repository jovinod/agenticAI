import datetime
from typing import Optional
from pgvector.sqlalchemy import Vector
from sqlmodel import SQLModel, Field, UniqueConstraint, Column

# One row per (job_id, ticker) — a single "job_id" from the frontend's point of view
# now fans out into one row per requested ticker, processed independently.
class TickerJob(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("job_id", "ticker"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True)          # shared across all tickers in one request — no longer unique alone
    ticker: str = Field(index=True)
    market: str = "US"                        # "US" or "India" — user-selected, not auto-detected
    status: str = "queued"
    result: Optional[str] = None             # JSON string, for now
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


# Read-side duplicate of backend/embed-worker/models.py's ResearchReport --
# only embed-worker writes this table, only this API reads it (for /search).
# Same reasoning as TickerJob's own duplication across projects.
EMBEDDING_DIM = 1536

class ResearchReport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True)
    ticker: str
    market: str
    report_text: str
    embedding: list[float] = Field(sa_column=Column(Vector(EMBEDDING_DIM)))
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
