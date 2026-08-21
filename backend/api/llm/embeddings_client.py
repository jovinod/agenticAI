"""
First time this API has ever called Foundry directly -- every prior LLM call
lived in the worker. Needed here because a human's free-form search query has
to be embedded before it can be compared against stored report vectors, and
that embedding has to happen synchronously in the request/response cycle
(the person asking wants an answer now, not a queued job). Same APIM
gateway, same managed-identity auth as backend/worker/llm/model_client.py
and backend/embed-worker/embeddings_client.py -- kept as its own copy since
none of these three projects share an import path.
"""
import os
import httpx

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
