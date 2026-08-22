"""
Phase 8 -- Entra ID answers "is this really who they say they are." That's
authentication, and it's all fastapi-azure-auth does. It does NOT answer
"should this specific person be allowed to use this app" -- that's a
separate question (authorization), and by design Entra ID alone can't
answer it: opening sign-in to any Microsoft account (needed later for a
family member to sign in with their own account) would otherwise mean
literally anyone with a Microsoft account could reach this API. The
allow-list below is that second, explicit check.
"""
import os
from fastapi import Depends, HTTPException
from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer
from fastapi_azure_auth.user import User

TENANT_ID = os.environ["ENTRA_TENANT_ID"]
CLIENT_ID = os.environ["ENTRA_CLIENT_ID"]
API_SCOPE = os.environ["ENTRA_API_SCOPE"]  # api://<client-id>/access_as_user

# Comma-separated real email addresses -- not a secret (these are just
# addresses, not credentials), so a plain env var, same as ALLOWED_ORIGIN.
ALLOWED_USERS = {
    email.strip().lower()
    for email in os.environ.get("ALLOWED_USERS", "").split(",")
    if email.strip()
}

azure_scheme = SingleTenantAzureAuthorizationCodeBearer(
    # Confirmed by decoding two real live tokens, not assumed: a v1.0 token's
    # `aud` was the App ID URI (api://<client-id>), but after switching the
    # app registration to issue v2.0 tokens, `aud` flipped to the bare
    # Client ID instead -- the opposite format. Real, slightly
    # counter-intuitive Entra ID behavior when the same app registration is
    # both the client and the API scope being requested (this project's
    # exact setup): v2.0 tokens use the bare GUID here, not the URI.
    app_client_id=CLIENT_ID,
    tenant_id=TENANT_ID,
    scopes={API_SCOPE: "Access alpha-research as the signed-in user"},
    # This tenant was created from a personal Microsoft account (hotmail.com),
    # so Entra ID represents even the tenant owner's own sign-in with an `idp`
    # claim that differs from `iss` -- the library's is_guest() heuristic
    # reads that as "guest" even though it's the actual admin. Our own
    # require_user allow-list below is the real authorization boundary
    # regardless, so relaxing this specific Entra-level check doesn't widen
    # who can actually use the app.
    allow_guest_users=True,
)


async def require_user(user: User = Depends(azure_scheme)) -> User:
    username = (user.preferred_username or user.email or "").lower()
    if username not in ALLOWED_USERS:
        raise HTTPException(status_code=403, detail="Not authorized to use this application.")
    return user
