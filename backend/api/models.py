import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True, unique=True)
    tickers: str  # JSON-encoded list
    status: str = "queued"
    result: Optional[str] = None  # JSON-encoded dict
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
