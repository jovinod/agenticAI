import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, SQLModel, create_engine, select

from auth import azure_scheme, require_user
from models import Job

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:devpassword@localhost:5433/alpha"
)
SERVICEBUS_CONNECTION_STRING = os.environ.get("SERVICEBUS_CONNECTION_STRING")
SERVICEBUS_QUEUE_NAME = os.environ.get("SERVICEBUS_QUEUE_NAME", "research-jobs")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:5173")

engine = create_engine(DATABASE_URL)
SQLModel.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await azure_scheme.openid_config.load_config()
    app.state.servicebus_client = ServiceBusClient.from_connection_string(
        SERVICEBUS_CONNECTION_STRING
    )
    yield
    await app.state.servicebus_client.close()


app = FastAPI(title="Stock Research API", lifespan=lifespan)

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
async def create_research(
    request: ResearchRequest, user=Depends(require_user)
) -> dict[str, str]:
    job_id = str(uuid.uuid4())

    with Session(engine) as session:
        session.add(Job(job_id=job_id, tickers=json.dumps(request.tickers)))
        session.commit()

    message = ServiceBusMessage(
        json.dumps({"job_id": job_id, "tickers": request.tickers})
    )
    async with app.state.servicebus_client.get_queue_sender(
        queue_name=SERVICEBUS_QUEUE_NAME
    ) as sender:
        await sender.send_messages(message)

    return {"job_id": job_id, "status": "accepted"}


@app.get("/research/{job_id}")
async def get_research(job_id: str, user=Depends(require_user)) -> dict[str, Any]:
    with Session(engine) as session:
        job = session.exec(select(Job).where(Job.job_id == job_id)).first()

    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    return {
        "status": job.status,
        "result": json.loads(job.result) if job.result else None,
    }
