import { useState } from 'react'
import { useMsal, AuthenticatedTemplate, UnauthenticatedTemplate } from '@azure/msal-react'
import { InteractionRequiredAuthError } from '@azure/msal-browser'
import { loginRequest } from './authConfig.js'
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

    try {
      const token = await getAccessToken()
      const response = await fetch(`${API_URL}/research`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ tickers: parsed, market }),
      })
      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`)
      }
      const { job_id } = await response.json()
      pollStatus(job_id)
    } catch (err) {
      setError('Could not reach the server. Check that the backend is running and try again.')
      setStatus('idle')
    }
  }

  // Service Bus delivery can genuinely take up to ~60s sometimes (a known, logged
  // quirk — see concepts.md) — this cap is for a truly unresponsive backend, not
  // ordinary slowness, so it's set generously rather than tightly.
  const MAX_POLL_ATTEMPTS = 120 // 1/sec => 2 minutes

  function pollStatus(jobId) {
    let attempts = 0

    const interval = setInterval(async () => {
      attempts += 1

      try {
        const token = await getAccessToken()
        const response = await fetch(`${API_URL}/research/${jobId}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!response.ok) {
          throw new Error(`Server returned ${response.status}`)
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
      } catch (err) {
        clearInterval(interval)
        setError('Lost connection to the server while waiting for results. Please try again.')
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
          <h2>Report</h2>
          <ul>
            {report.summary.map((line) => <li key={line}>{line}</li>)}
          </ul>
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
