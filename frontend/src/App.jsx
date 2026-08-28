import { useState } from 'react'
import { useMsal, AuthenticatedTemplate, UnauthenticatedTemplate } from '@azure/msal-react'
import { InteractionRequiredAuthError } from '@azure/msal-browser'
import { loginRequest } from './authConfig.js'
import ReportView from './ReportView.jsx'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function SignInScreen() {
  const { instance } = useMsal()
  return (
    <div id="center">
      <h1>Alpha - Stock Research</h1>
      <p>Please sign in to continue.</p>
      <button onClick={() => instance.loginRedirect(loginRequest)}>Sign in with Microsoft</button>
    </div>
  )
}

function ResearchApp() {
  const { instance, accounts } = useMsal()
  const [tickerInput, setTickerInput] = useState('')
  const [market, setMarket] = useState('US')
  const [tickers, setTickers] = useState([])
  const [error, setError] = useState('')
  const [status, setStatus] = useState('idle') // 'idle' | 'loading' | 'done'
  const [report, setReport] = useState(null)

  // acquireTokenSilent uses MSAL's own cache and only makes a real network
  // call when the cached token is actually close to expiring -- calling this
  // before every request (rather than threading a token through state) is
  // the normal MSAL pattern, not wasteful the way it might look at first.
  async function getAccessToken() {
    const request = { ...loginRequest, account: accounts[0] }
    try {
      const result = await instance.acquireTokenSilent(request)
      return result.accessToken
    } catch (err) {
      if (err instanceof InteractionRequiredAuthError) {
        const result = await instance.acquireTokenPopup(request)
        return result.accessToken
      }
      throw err
    }
  }

  // Every failure used to fall into one generic "could not reach the server"
  // message -- a real problem found live: an expired session, a 401/403 from
  // a genuinely reachable server, and an actual network failure all looked
  // identical to the user, which made a session-expiry issue look like a
  // backend outage. describeResponseError covers the "we got an HTTP
  // response, just not a good one" case; callers handle the token-acquisition
  // and network-failure cases directly, since those never reach a response.
  function describeResponseError(response) {
    if (response.status === 401 || response.status === 403) {
      return 'Your session has expired or you are not authorized. Please sign in again.'
    }
    return `Server error (${response.status}). Please try again in a moment.`
  }

  async function handleSubmit() {
    const parsed = tickerInput
      .split(',')
      .map((t) => t.trim().toUpperCase())
      .filter((t) => t.length > 0)

    if (parsed.length === 0) {
      setError('Please enter at least one ticker.')
      return
    }

    const invalid = parsed.filter((t) => !/^[A-Z]{1,5}$/.test(t))
    if (invalid.length > 0) {
      setError(`Invalid ticker format: ${invalid.join(', ')}`)
      return
    }

    setError('')
    setTickers(parsed)
    setStatus('loading')

    let token
    try {
      token = await getAccessToken()
    } catch (err) {
      setError('Your session has expired. Please sign in again.')
      setStatus('idle')
      return
    }

    let response
    try {
      response = await fetch(`${API_URL}/research`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ tickers: parsed, market }),
      })
    } catch (err) {
      setError('Could not reach the server. Check your connection and try again.')
      setStatus('idle')
      return
    }

    if (!response.ok) {
      setError(describeResponseError(response))
      setStatus('idle')
      return
    }

    const { job_id } = await response.json()
    pollStatus(job_id)
  }

  // Service Bus delivery can genuinely take up to ~60s sometimes (a known, logged
  // quirk — see concepts.md) — this cap is for a truly unresponsive backend, not
  // ordinary slowness, so it's set generously rather than tightly.
  const MAX_POLL_ATTEMPTS = 120 // 1/sec => 2 minutes

  function pollStatus(jobId) {
    let attempts = 0

    const interval = setInterval(async () => {
      attempts += 1

      let token
      try {
        token = await getAccessToken()
      } catch (err) {
        clearInterval(interval)
        setError('Your session has expired. Please sign in again.')
        setStatus('idle')
        return
      }

      let response
      try {
        response = await fetch(`${API_URL}/research/${jobId}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
      } catch (err) {
        clearInterval(interval)
        setError('Lost connection to the server while waiting for results. Please try again.')
        setStatus('idle')
        return
      }

      if (!response.ok) {
        clearInterval(interval)
        setError(describeResponseError(response))
        setStatus('idle')
        return
      }

      const data = await response.json()

      if (data.status === 'done') {
        clearInterval(interval)
        setReport(data.result)
        setStatus('done')
        return
      }
      if (data.error) {
        clearInterval(interval)
        setError(`Something went wrong: ${data.error}`)
        setStatus('idle')
        return
      }

      if (attempts >= MAX_POLL_ATTEMPTS) {
        clearInterval(interval)
        setError('This is taking much longer than expected. Please try again.')
        setStatus('idle')
      }
    }, 1000)
  }

  function handleReset() {
    setStatus('idle')
    setTickerInput('')
    setTickers([])
    setReport(null)
  }

  return (
    <div id="center">
      <h1>Alpha - Stock Research</h1>

      {status === 'idle' && (
        <>
          <select value={market} onChange={(e) => setMarket(e.target.value)}>
            <option value="US">US market</option>
            <option value="India">India market (NSE/BSE)</option>
          </select>
          <input
            type="text"
            placeholder={market === 'US' ? 'e.g. AAPL, TSLA' : 'e.g. RELIANCE, TCS'}
            value={tickerInput}
            onChange={(e) => setTickerInput(e.target.value)}
          />
          <button onClick={handleSubmit}>Analyze</button>
          {error && <p className="error">{error}</p>}
        </>
      )}

      {status === 'loading' && <p>Analyzing {tickers.join(', ')}...</p>}

      {status === 'done' && report && (
        <div>
          <ReportView report={report} />
          <button onClick={handleReset}>New search</button>
        </div>
      )}
    </div>
  )
}

function App() {
  return (
    <>
      <AuthenticatedTemplate>
        <ResearchApp />
      </AuthenticatedTemplate>
      <UnauthenticatedTemplate>
        <SignInScreen />
      </UnauthenticatedTemplate>
    </>
  )
}

export default App
