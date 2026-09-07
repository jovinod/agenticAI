import os
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from job_store import JobStore

DATABASE_PATH = os.getenv("DATABASE_PATH", "jobs.db")
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "http://localhost:5173")

app = FastAPI(title="Stock Research API")
store = JobStore(DATABASE_PATH)

# CORS is a browser-facing access rule, not authentication -- it only
# controls which origins a browser will let JavaScript read a response
# from. The frontend's dev server runs on a different origin (port) than
# this API during local development, so without this, the browser would
# block every request.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    tickers: list[str] = Field(min_length=1)

    @field_validator("tickers")
    @classmethod
    def normalize_tickers(cls, tickers: list[str]) -> list[str]:
        normalized = [ticker.strip().upper() for ticker in tickers]
        if any(not ticker.isalpha() or len(ticker) > 5 for ticker in normalized):
            raise ValueError("tickers must contain 1-5 letters")
        return normalized


@app.post("/research", status_code=202)
async def create_research(request: ResearchRequest) -> dict[str, str]:
    job_id = str(uuid.uuid4())
    store.create_job(job_id, request.tickers)
    return {"job_id": job_id, "status": "accepted"}


@app.get("/research/{job_id}")
async def get_research(job_id: str) -> dict[str, Any]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    return {"status": job["status"], "result": job["result"]}
