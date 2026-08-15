"""
Thin wrapper around whichever model backend is actually answering right now.
Everything else in the agent talks to `chat()` and only `chat()` -- swapping
Ollama for Azure AI Foundry later means changing what's inside this one
function, not touching the agent loop, the Context Assembler, or the tools.
"""
import requests

MODEL = "qwen3:8b"
OLLAMA_URL = "http://localhost:11434/api/chat"


def chat(messages: list[dict], tools: list[dict]) -> dict:
    """Send messages + tool schemas to the model, return its response message."""
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "tools": tools, "stream": False},
    )
    response.raise_for_status()
    return response.json()["message"]
