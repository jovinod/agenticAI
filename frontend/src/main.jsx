import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { PublicClientApplication } from '@azure/msal-browser'
import { MsalProvider } from '@azure/msal-react'
import './index.css'
import App from './App.jsx'
import { msalConfig } from './authConfig.js'

const msalInstance = new PublicClientApplication(msalConfig)
await msalInstance.initialize()

// Popup-based sign-in depends on the opener window being able to poll
// the popup's location -- Static Web Apps' default Cross-Origin-Opener-
// Policy headers block that, so the popup completes the exchange but
// never reports back or closes itself. Redirect-based sign-in avoids
// popup/window access entirely: the whole page navigates to Entra and
// back, and this call picks up the response on return.
await msalInstance.handleRedirectPromise()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <MsalProvider instance={msalInstance}>
      <App />
    </MsalProvider>
  </StrictMode>,
)
