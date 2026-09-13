import os

import httpx
from azure.identity import DefaultAzureCredential

CONTENT_SAFETY_ENDPOINT = os.environ.get("CONTENT_SAFETY_ENDPOINT", "")
API_VERSION = "2024-09-01"

# Real hard limit: 10,000 characters total across all documents in one
# request. Exceeding it is a 400, not a classifier verdict, so the news
# node truncates before calling this rather than treating it as unsafe.
MAX_TOTAL_CHARACTERS = 10_000

_credential = DefaultAzureCredential()


async def scan_documents(documents: list[str]) -> list[bool]:
    """Prompt Shields for Documents classifies retrieved text for
    indirect prompt injection before it reaches model context. True
    means safe to continue.

    A missing endpoint is a fail-open policy, not classifier approval
    -- it supports local development, and the honest label for this
    path is unscanned pass-through.
    """
    if not CONTENT_SAFETY_ENDPOINT or not documents:
        return [True] * len(documents)

    token = _credential.get_token(
        "https://cognitiveservices.azure.com/.default"
    ).token

    url = f"{CONTENT_SAFETY_ENDPOINT}/contentsafety/text:shieldPrompt"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            params={"api-version": API_VERSION},
            headers={"Authorization": f"Bearer {token}"},
            json={"userPrompt": "", "documents": documents},
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()

    return [
        not result["attackDetected"] for result in body["documentsAnalysis"]
    ]
