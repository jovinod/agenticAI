export const msalConfig = {
  auth: {
    clientId: import.meta.env.VITE_ENTRA_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_ENTRA_TENANT_ID}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage',
  },
}

// Client ID, tenant ID, and this scope are identifiers, not
// credentials -- they can appear in compiled frontend code. Registered
// redirects, PKCE, signed tokens, server-side validation, and
// authorization policy provide the actual protection.
export const loginRequest = {
  scopes: [import.meta.env.VITE_ENTRA_API_SCOPE],
}
