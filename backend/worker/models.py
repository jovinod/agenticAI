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
    status: str = "queued"
    result: Optional[str] = None
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
