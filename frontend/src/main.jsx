import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { PublicClientApplication, EventType } from '@azure/msal-browser'
import { MsalProvider } from '@azure/msal-react'
import './index.css'
import App from './App.jsx'
import { msalConfig } from './authConfig.js'

const msalInstance = new PublicClientApplication(msalConfig)

// MSAL doesn't automatically know which signed-in account to use if more than
// one exists (e.g. someone already had two Microsoft accounts signed in on
// this browser) -- explicitly set the active account after a successful
// login, otherwise later token requests have nothing to attach to.
msalInstance.addEventCallback((event) => {
  if (event.eventType === EventType.LOGIN_SUCCESS && event.payload.account) {
    msalInstance.setActiveAccount(event.payload.account)
  }
})

await msalInstance.initialize()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <MsalProvider instance={msalInstance}>
      <App />
    </MsalProvider>
  </StrictMode>,
)
