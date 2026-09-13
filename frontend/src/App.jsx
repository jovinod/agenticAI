import { useEffect, useState } from 'react'
import { useMsal } from '@azure/msal-react'
import { InteractionRequiredAuthError } from '@azure/msal-browser'
import './App.css'
import { loginRequest } from './authConfig.js'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Bounded polling: the frontend checks at most this many times, waiting
// this long between checks. Waiting must have a defined end -- the exact
// numbers are a temporary policy choice, not a load-bearing contract.
const MAX_POLL_ATTEMPTS = 20
const POLL_INTERVAL_MS = 500

function App() {
  const { instance, accounts } = useMsal()
  const [tab, setTab] = useState('research') // 'research' | 'history'
  const [tickerInput, setTickerInput] = useState('')
  const [tickers, setTickers] = useState([])
  const [error, setError] = useState('')
  const [status, setStatus] = useState('idle') // 'idle' | 'loading' | 'done'
  const [report, setReport] = useState(null)
  const [copied, setCopied] = useState(false)

  const [history, setHistory] = useState([])
  const [historyFilter, setHistoryFilter] = useState('')
  const [historyError, setHistoryError] = useState('')

  // Authenticated UI state is useful feedback, not security -- a
  // caller can bypass this entirely and invoke the API directly. The
  // browser's real responsibility is acquiring a token for the API
  // scope and attaching it to every protected request.
  async function getAccessToken() {
    const account = accounts[0]
    try {
      const result = await instance.acquireTokenSilent({ ...loginRequest, account })
      return result.accessToken
    } catch (err) {
      if (err instanceof InteractionRequiredAuthError) {
        // Navigates away -- there is no token to return from this
        // branch. The in-flight request is abandoned; the page comes
        // back after Entra redirects here again.
        await instance.acquireTokenRedirect(loginRequest)
        return
      }
      throw err
    }
  }

  async function authedFetch(url, options = {}) {
    const token = await getAccessToken()
    return fetch(url, {
      ...options,
      headers: { ...options.headers, Authorization: `Bearer ${token}` },
    })
  }

  async function pollJob(jobId) {
    for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))

      let response
      try {
        response = await authedFetch(`${API_URL}/research/${jobId}`)
      } catch (err) {
        setError('Lost connection to the server while waiting for results.')
        setStatus('idle')
        return
      }

      if (response.status === 401) {
        setError('Your session expired. Please sign in again.')
        setStatus('idle')
        return
      }
      if (response.status === 403) {
        setError('You are not authorized to use this application.')
        setStatus('idle')
        return
      }
      if (!response.ok) {
        setError(`The API returned ${response.status}.`)
        setStatus('idle')
        return
      }

      const job = await response.json()

      if (job.status === 'done') {
        setReport({ jobId, ...job.result })
        setStatus('done')
        return
      }
      if (job.status === 'failed') {
        setError('The research job failed.')
        setStatus('idle')
        return
      }
    }

    setError('The research job took too long.')
    setStatus('idle')
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
    setCopied(false)
    setTickers(parsed)
    setStatus('loading')

    let response
    try {
      response = await authedFetch(`${API_URL}/research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers: parsed }),
      })
    } catch (err) {
      setError('Could not reach the server. Check your connection and try again.')
      setStatus('idle')
      return
    }

    if (response.status === 401) {
      setError('Your session expired. Please sign in again.')
      setStatus('idle')
      return
    }
    if (response.status === 403) {
      setError('You are not authorized to use this application.')
      setStatus('idle')
      return
    }
    if (!response.ok) {
      setError(`The API returned ${response.status}.`)
      setStatus('idle')
      return
    }

    const { job_id } = await response.json()
    await pollJob(job_id)
  }

  function handleReset() {
    setStatus('idle')
    setTickerInput('')
    setTickers([])
    setReport(null)
    setCopied(false)
  }

  async function handleCopyJobId() {
    if (!report) return
    await navigator.clipboard.writeText(report.jobId)
    setCopied(true)
  }

  async function loadHistory() {
    setHistoryError('')
    let response
    try {
      const url = new URL(`${API_URL}/reports`)
      if (historyFilter.trim()) {
        url.searchParams.set('ticker', historyFilter.trim())
      }
      response = await authedFetch(url)
    } catch (err) {
      setHistoryError('Could not reach the server. Check your connection and try again.')
      return
    }

    if (response.status === 401 || response.status === 403) {
      setHistoryError('Your session has expired or you are not authorized. Please sign in again.')
      return
    }
    if (!response.ok) {
      setHistoryError(`The API returned ${response.status}.`)
      return
    }

    setHistory(await response.json())
  }

  // Records load without an initial search -- history is visible the
  // moment the tab opens, not only after the user acts.
  useEffect(() => {
    if (tab === 'history') {
      loadHistory()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab])

  async function handleOpenHistoryRow(jobId) {
    setTab('research')
    setStatus('loading')
    setError('')
    setCopied(false)

    let response
    try {
      response = await authedFetch(`${API_URL}/research/${jobId}`)
    } catch (err) {
      setError('Lost connection to the server.')
      setStatus('idle')
      return
    }
    if (!response.ok) {
      setError(`The API returned ${response.status}.`)
      setStatus('idle')
      return
    }

    const job = await response.json()
    setReport({ jobId, ...job.result })
    setTickers(job.result?.tickers ?? [])
    setStatus('done')
  }

  if (accounts.length === 0) {
    return (
      <div id="center">
        <h1>Stock Research Assistant</h1>
        <button onClick={() => instance.loginRedirect(loginRequest)}>Sign in</button>
      </div>
    )
  }

  return (
    <div id="center">
      <h1>Stock Research Assistant</h1>

      <nav className="tabs">
        <button
          className={tab === 'research' ? 'tab active' : 'tab'}
          onClick={() => setTab('research')}
        >
          New Research
        </button>
        <button
          className={tab === 'history' ? 'tab active' : 'tab'}
          onClick={() => setTab('history')}
        >
          History
        </button>
      </nav>

      {tab === 'research' && (
        <>
          {status === 'idle' && (
            <>
              <input
                type="text"
                placeholder="e.g. AAPL, TSLA"
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
              <p className="job-id-line">
                Job ID: <code>{report.jobId}</code>{' '}
                <button className="copy-btn" onClick={handleCopyJobId}>
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </p>
              <button onClick={handleReset}>New search</button>
            </div>
          )}
        </>
      )}

      {tab === 'history' && (
        <div className="history">
          <div className="history-filter">
            <input
              type="text"
              placeholder="Filter by ticker"
              value={historyFilter}
              onChange={(e) => setHistoryFilter(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && loadHistory()}
            />
            <button onClick={loadHistory}>Filter</button>
          </div>

          {historyError && <p className="error">{historyError}</p>}

          <table className="history-table">
            <thead>
              <tr>
                <th>Tickers</th>
                <th>Date</th>
                <th>Job ID</th>
              </tr>
            </thead>
            <tbody>
              {history.map((row) => (
                <tr key={row.job_id} onClick={() => handleOpenHistoryRow(row.job_id)}>
                  <td>{row.tickers.join(', ')}</td>
                  <td>{new Date(row.created_at).toLocaleString()}</td>
                  <td><code>{row.job_id}</code></td>
                </tr>
              ))}
            </tbody>
          </table>

          {history.length === 0 && !historyError && <p>No completed reports yet.</p>}
        </div>
      )}
    </div>
  )
}

export default App
