# Duplicated from backend/api/models.py — see decisions.md ("Database library") for why.
# TODO: extract to a real shared package if these drift out of sync becomes painful.
import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, UniqueConstraint

class TickerJob(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("job_id", "ticker"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True)
    ticker: str = Field(index=True)
    market: str = "US"                        # "US" or "India" — user-selected, not auto-detected
    status: str = "queued"
    result: Optional[str] = None
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


# Worker-only, not duplicated into backend/api/models.py -- unlike TickerJob, only the
# worker ever writes or reads this (one agent run -> one row, right after run_agent
# returns). Nothing on the API side needs it yet, so it doesn't get the same
# dual-copy treatment TickerJob needed for its genuine dual read/write need.
class TokenUsage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True)
    ticker: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
