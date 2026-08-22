// Entra ID app registration details. None of these are secrets -- a SPA can't
// hold a secret anyway (see book/chapter-08), and the actual security comes
// from Entra ID only trusting the registered redirect URI plus PKCE, not from
// hiding these values.
export const msalConfig = {
  auth: {
    clientId: import.meta.env.VITE_ENTRA_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_ENTRA_TENANT_ID}`,
    redirectUri: import.meta.env.VITE_ENTRA_REDIRECT_URI || window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage',
  },
}

// The API scope exposed on the app registration -- requested up front during
// sign-in, so the resulting token already carries the right audience marker
// for our API by the time we need it.
export const loginRequest = {
  scopes: [import.meta.env.VITE_ENTRA_API_SCOPE],
}
