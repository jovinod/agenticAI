"""Shared Redis client -- worker.py's result cache and memory/short_term.py's
progress tracking both need the exact same connection, so this lives here
once rather than duplicated within this project (unlike TickerJob/
ResearchReport, which duplicate ACROSS the three separate backend projects)."""
import os
import redis.asyncio as redis

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6380"))
REDIS_SSL = os.environ.get("REDIS_SSL", "false").lower() == "true"

# Phase 8, Stage C -- Managed Identity instead of a password secret, when
# running in Azure. Same reasoning as Postgres: the local Docker Redis
# container has no AAD support at all, so this is a genuine second code
# path, not a same-code-either-way fallback like Service Bus's. Unlike
# Postgres, a Redis connection needs its token refreshed and re-AUTH'd
# periodically for the life of the connection (not just once at connect
# time) -- redis-entraid's CredentialProvider handles that refresh loop.
REDIS_USE_ENTRA_AUTH = os.environ.get("REDIS_USE_ENTRA_AUTH", "false").lower() == "true"

if REDIS_USE_ENTRA_AUTH:
    from redis_entraid.cred_provider import create_from_default_azure_credential

    REDIS_TOKEN_SCOPE = "https://redis.azure.com/.default"
    _credential_provider = create_from_default_azure_credential(scopes=(REDIS_TOKEN_SCOPE,))

    redis_client = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, ssl=REDIS_SSL,
        credential_provider=_credential_provider, decode_responses=True,
    )
else:
    REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")  # unset locally
    redis_client = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, ssl=REDIS_SSL,
        decode_responses=True,
    )
