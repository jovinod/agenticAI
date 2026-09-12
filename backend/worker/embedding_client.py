import os

import httpx

APIM_BASE_URL = os.environ.get("APIM_BASE_URL", "")
APIM_SUBSCRIPTION_KEY = os.environ.get("APIM_SUBSCRIPTION_KEY", "")
API_VERSION = os.environ.get("APIM_API_VERSION", "2024-10-21")
EMBED_URL = f"{APIM_BASE_URL}/openai/deployments/embed/embeddings"


async def embed_query(text: str) -> list[float]:
    """The API scrubs PII from free text and embeds the query with the
    same model family used to index reports, before ranking by
    similarity -- not injected into any agent's context."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            EMBED_URL,
            params={"api-version": API_VERSION},
            headers={
                "Ocp-Apim-Subscription-Key": APIM_SUBSCRIPTION_KEY,
                "Content-Type": "application/json",
            },
            json={"input": text},
        )
        response.raise_for_status()
        body = response.json()
    return body["data"][0]["embedding"]
