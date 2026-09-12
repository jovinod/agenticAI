import os

from fastapi import Depends, HTTPException
from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer
from fastapi_azure_auth.user import User

CLIENT_ID = os.environ.get("ENTRA_CLIENT_ID", "")
TENANT_ID = os.environ.get("ENTRA_TENANT_ID", "")
API_SCOPE = f"api://{CLIENT_ID}/access_as_user"

# The tenant here originated from a personal Microsoft account. The
# library's guest heuristic classifies the tenant owner as a guest
# because the token's idp and iss claims differ (idp: live.com, iss:
# this tenant's own issuer). Allowing that library-level case is
# specific to this tenant's identity model -- it is not the product
# authorization rule. ALLOWED_USERS below is the real boundary.
azure_scheme = SingleTenantAzureAuthorizationCodeBearer(
    app_client_id=CLIENT_ID,
    tenant_id=TENANT_ID,
    scopes={API_SCOPE: "Access alpha-research as the signed-in user"},
    allow_guest_users=True,
)

ALLOWED_USERS = {
    email.strip().lower()
    for email in os.environ.get("ALLOWED_USERS", "").split(",")
    if email.strip()
}


async def require_user(user: User = Depends(azure_scheme)) -> User:
    """A valid token means Entra issued it for this subject and this
    API. It does not mean the application's owner permits that subject
    to use the product -- that is this separate, second decision."""
    username = (user.preferred_username or user.email or "").lower()
    if username not in ALLOWED_USERS:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to use this application.",
        )
    return user
