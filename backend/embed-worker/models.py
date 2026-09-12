import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column
from sqlmodel import Field, SQLModel

# Matches Azure OpenAI's text-embedding-3-small output dimension.
EMBEDDING_DIM = 1536


class ResearchReport(SQLModel, table=True):
    __tablename__ = "research_reports"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True)
    ticker: str
    market: str
    report_text: str
    embedding: list[float] = Field(sa_column=Column(Vector(EMBEDDING_DIM)))
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
