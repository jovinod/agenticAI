import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, UniqueConstraint

# One row per (job_id, ticker) — a single "job_id" from the frontend's point of view
# now fans out into one row per requested ticker, processed independently.
class TickerJob(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("job_id", "ticker"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True)          # shared across all tickers in one request — no longer unique alone
    ticker: str = Field(index=True)
    status: str = "queued"
    result: Optional[str] = None             # JSON string, for now
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
