import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True, unique=True)
    tickers: str          # comma-separated for now — simplest first pass
    status: str = "queued"
    result: Optional[str] = None  # JSON string, for now
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
