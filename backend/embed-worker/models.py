# Duplicated from backend/api/models.py -- see decisions.md ("Database library")
# for why. This project only ever WRITES ResearchReport (backend/api reads it
# for the /search endpoint), so it doesn't need TickerJob or any other table.
import datetime
from typing import Optional
from pgvector.sqlalchemy import Vector
from sqlmodel import SQLModel, Field, Column

# text-embedding-3-small's native dimension count.
EMBEDDING_DIM = 1536


class ResearchReport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True)
    ticker: str
    market: str
    report_text: str
    embedding: list[float] = Field(sa_column=Column(Vector(EMBEDDING_DIM)))
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
