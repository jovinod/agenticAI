import os
import uuid
from contextlib import asynccontextmanager
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from sqlmodel import create_engine, Session, select
from models import Job

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:devpassword@localhost:5433/alpha"
)
engine = create_engine(DATABASE_URL)

SERVICEBUS_CONNECTION_STRING = os.environ.get("SERVICEBUS_CONNECTION_STRING")
SERVICEBUS_QUEUE_NAME = os.environ.get("SERVICEBUS_QUEUE_NAME", "research-jobs")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:5173")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.servicebus_client = ServiceBusClient.from_connection_string(
        SERVICEBUS_CONNECTION_STRING
    )
    yield
    await app.state.servicebus_client.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    tickers: list[str]


@app.get("/")
def read_root():
    return {"status": "ok"}


@app.post("/research")
async def create_research(request: ResearchRequest):
    job_id = str(uuid.uuid4())

    with Session(engine) as session:
        job = Job(job_id=job_id, tickers=",".join(request.tickers), status="queued")
        session.add(job)
        session.commit()

    message_body = json.dumps({"job_id": job_id, "tickers": request.tickers})
    async with app.state.servicebus_client.get_queue_sender(
        queue_name=SERVICEBUS_QUEUE_NAME
    ) as sender:
        await sender.send_messages(ServiceBusMessage(message_body))

    return {"job_id": job_id}


@app.get("/research/{job_id}")
async def get_research(job_id: str):
    with Session(engine) as session:
        job = session.exec(select(Job).where(Job.job_id == job_id)).first()

    if job is None:
        return {"error": "not found"}

    return {
        "status": job.status,
        "result": json.loads(job.result) if job.result else None,
    }
