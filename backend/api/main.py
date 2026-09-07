import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

app = FastAPI()

# CORS is a browser-facing access rule, not authentication -- it only
# controls which origins a browser will let JavaScript read a response
# from. The frontend's dev server runs on a different origin (port) than
# this API during local development, so without this, the browser would
# block every request.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Intentionally temporary: a real deadline in a real Chapter 3 worker
# doesn't exist yet, so this stands in for "the work is still running."
JOB_DELAY_SECONDS = 2.0

# Intentionally temporary: process-local, in-memory job storage. It lets
# the status route look a job up by ID without introducing a database
# before that responsibility is actually needed. Every job disappears if
# this process restarts -- Chapter 3 replaces this with PostgreSQL.
jobs: dict[str, dict[str, Any]] = {}


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
    jobs[job_id] = {
        "status": "running",
        "tickers": request.tickers,
        "ready_at": time.monotonic() + JOB_DELAY_SECONDS,
    }
    return {"job_id": job_id, "status": "accepted"}


@app.get("/research/{job_id}")
async def get_research(job_id: str) -> dict[str, Any]:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    if time.monotonic() < job["ready_at"]:
        return {"status": "running", "result": None}

    result = {
        "summary": [
            f"{ticker}: looks solid, no major red flags." for ticker in job["tickers"]
        ],
    }
    return {"status": "done", "result": result}
