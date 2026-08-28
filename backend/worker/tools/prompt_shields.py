"""
Prompt Shields for Documents -- Azure AI Content Safety's real, GA service for
exactly one problem: content an agent is asked to read (a search result, a
document) that contains hidden instructions meant to hijack the model, as
opposed to a direct user message (already covered by Azure OpenAI's own
built-in jailbreak classifier -- confirmed live, see book/chapter-09-guardrails.md).

Called specifically from tools/web_search.py, the one place untrusted
external web content enters this project. Not wired into agent_harness.py's
shared _call_tool -- every OTHER tool (compute_intrinsic_value,
check_hard_stop_rules, fetch_stock_data, technical_indicators) returns
either a deterministic computation or data this project's own code fetched
directly, with nothing for a third party to have hidden text inside.
Scanning those would just be added latency and cost for zero real risk.
"""
import os
from azure.identity import DefaultAzureCredential

CONTENT_SAFETY_ENDPOINT = os.environ.get("CONTENT_SAFETY_ENDPOINT")
_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"
_credential = DefaultAzureCredential() if CONTENT_SAFETY_ENDPOINT else None


async def scan_documents(documents: list[str]) -> list[bool]:
    """Returns one bool per document, True if that document is safe to hand
    to the model, False if Prompt Shields flagged it as a likely injection
    attempt. If CONTENT_SAFETY_ENDPOINT isn't set (local dev without this
    resource configured), everything passes through unscanned -- the same
    "no-op locally" shape as every other Azure-only feature in this project."""
    if not CONTENT_SAFETY_ENDPOINT or not documents:
        return [True] * len(documents)

    import httpx

    token = _credential.get_token(_TOKEN_SCOPE).token
    url = f"{CONTENT_SAFETY_ENDPOINT.rstrip('/')}/contentsafety/text:shieldPrompt?api-version=2024-09-01"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"userPrompt": "", "documents": documents},
            timeout=15,
        )
    response.raise_for_status()
    analysis = response.json()["documentsAnalysis"]
    return [not doc["attackDetected"] for doc in analysis]
