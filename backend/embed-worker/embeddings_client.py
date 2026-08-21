"""
Thin wrapper around the embeddings deployment, same shape as
backend/worker/llm/model_client.py's chat() -- routes through the same APIM
gateway (managed-identity auth to Foundry, no raw key held here either).
Kept as its own small client rather than importing worker's model_client.py
directly, since backend/worker and backend/embed-worker are separate uv
projects with no shared import path (same reason TickerJob is duplicated
across backend/api and backend/worker).
"""
import os
import httpx
from dotenv import load_dotenv

load_dotenv(".env.local")

APIM_GATEWAY_URL = os.environ["APIM_GATEWAY_URL"].rstrip("/")
APIM_SUBSCRIPTION_KEY = os.environ["APIM_SUBSCRIPTION_KEY"]
AZURE_EMBEDDING_DEPLOYMENT = os.environ["AZURE_EMBEDDING_DEPLOYMENT"]
API_VERSION = "2024-08-01-preview"

EMBEDDINGS_URL = (
    f"{APIM_GATEWAY_URL}/openai/deployments/{AZURE_EMBEDDING_DEPLOYMENT}"
    f"/embeddings?api-version={API_VERSION}"
)


async def embed(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            EMBEDDINGS_URL,
            headers={"Ocp-Apim-Subscription-Key": APIM_SUBSCRIPTION_KEY, "Content-Type": "application/json"},
            json={"input": text},
        )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]
