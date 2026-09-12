import os

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

KEY_VAULT_URI = os.environ.get("KEY_VAULT_URI", "")
TAVILY_SECRET_NAME = "tavily-api-key"

_cached_key: str | None = None


def get_tavily_key() -> str:
    """Tavily cannot accept a managed identity token. Its key needs one
    authoritative home (Key Vault) and one intended reader (this
    service). Caching avoids a vault round trip on every search --
    Key Vault limits who can retrieve the key, but after retrieval the
    process can still log or misuse it, so this stays the only place
    that ever reads the raw value out of this module."""
    global _cached_key
    if _cached_key is None:
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=KEY_VAULT_URI, credential=credential)
        _cached_key = client.get_secret(TAVILY_SECRET_NAME).value
    return _cached_key
