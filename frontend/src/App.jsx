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

function ResearchTab({ getAccessToken }) {
  const [tickerInput, setTickerInput] = useState('')
  const [market, setMarket] = useState('US')
  const [tickers, setTickers] = useState([])
  const [error, setError] = useState('')
  const [status, setStatus] = useState('idle') // 'idle' | 'loading' | 'done'
  const [report, setReport] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [copied, setCopied] = useState(false)

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
    setJobId(job_id)
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
    setJobId(null)
    setCopied(false)
  }

  // Phase 10 -- the one thing a real bug report needs to be actionable: the
  // job_id that ties this report to a real trace in Application Insights
  // (see book/chapter-10-observability.md). Copy-to-clipboard makes "quote
  // this ID" a one-click action instead of a select-and-hope one.
  function handleCopyJobId() {
    navigator.clipboard.writeText(jobId)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <>
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
          {jobId && (
            <p className="job-id-line">
              Job ID: <code>{jobId}</code>{' '}
              <button className="copy-btn" onClick={handleCopyJobId}>
                {copied ? 'Copied' : 'Copy'}
              </button>
            </p>
          )}
        </div>
      )}
    </>
  )
}

// Phase 12 -- browsing past reports is a genuinely different read pattern
// from /search's semantic lookup (Chapter 5): filtering by the exact
// ticker/date key a user already has in mind, not "what did we say that's
// relevant to this." Reuses TickerJob rows the app already persists --
// no new storage, just a way to list/filter across jobs instead of one at
// a time, and the existing /research/{job_id} endpoint to fetch full detail.
function HistoryTab({ getAccessToken }) {
  const [tickerFilter, setTickerFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [reports, setReports] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedReport, setSelectedReport] = useState(null) // { ticker, report } once loaded

  async function handleSearch() {
    setError('')
    setLoading(true)
    setSelectedReport(null)

    let token
    try {
      token = await getAccessToken()
    } catch (err) {
      setError('Your session has expired. Please sign in again.')
      setLoading(false)
      return
    }

    const params = new URLSearchParams()
    if (tickerFilter.trim()) params.set('ticker', tickerFilter.trim().toUpperCase())
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)

    let response
    try {
      response = await fetch(`${API_URL}/reports?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
    } catch (err) {
      setError('Could not reach the server. Check your connection and try again.')
      setLoading(false)
      return
    }

    if (!response.ok) {
      setError(describeResponseError(response))
      setLoading(false)
      return
    }

    const data = await response.json()
    setReports(data.reports)
    setLoading(false)
  }

  async function handleSelect(entry) {
    setError('')
    setSelectedReport(null)

    let token
    try {
      token = await getAccessToken()
    } catch (err) {
      setError('Your session has expired. Please sign in again.')
      return
    }

    let response
    try {
      response = await fetch(`${API_URL}/research/${entry.job_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
    } catch (err) {
      setError('Could not reach the server. Check your connection and try again.')
      return
    }

    if (!response.ok) {
      setError(describeResponseError(response))
      return
    }

    const data = await response.json()
    if (data.status !== 'done') {
      setError('That report is no longer available.')
      return
    }

    // Narrow the (possibly multi-ticker) job result down to just the one
    // ticker selected from the list -- ReportView expects this exact shape,
    // including ticker_status so a historical failed ticker renders the
    // same distinct failure card the live flow does, not an empty state.
    const decision = data.result.decisions?.[entry.ticker]
    const summaryLines = (data.result.summary || []).filter((line) => line.startsWith(`${entry.ticker}:`))
    setSelectedReport({
      ticker: entry.ticker,
      report: {
        tickers: [entry.ticker],
        summary: summaryLines,
        decisions: decision ? { [entry.ticker]: decision } : {},
        ticker_status: data.result.ticker_status,
      },
    })
  }

  return (
    <div className="history-tab">
      <div className="history-filters">
        <input
          type="text"
          placeholder="Ticker (e.g. AAPL)"
          value={tickerFilter}
          onChange={(e) => setTickerFilter(e.target.value)}
        />
        <label>
          From <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label>
          To <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
        <button onClick={handleSearch} disabled={loading}>
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {reports && reports.length === 0 && <p>No reports found for that filter.</p>}

      {reports && reports.length > 0 && !selectedReport && (
        <ul className="history-list">
          {reports.map((r) => (
            <li key={`${r.job_id}:${r.ticker}`} className="history-item" onClick={() => handleSelect(r)}>
              <span className="history-ticker">{r.ticker}</span>
              <span className="history-market">{r.market}</span>
              <span className={`history-rec history-rec-${(r.recommendation || '').toLowerCase()}`}>
                {r.recommendation || 'N/A'}
              </span>
              <span className="history-date">{new Date(r.created_at).toLocaleString()}</span>
            </li>
          ))}
        </ul>
      )}

      {selectedReport && (
        <div>
          <button onClick={() => setSelectedReport(null)}>&larr; Back to list</button>
          <ReportView report={selectedReport.report} />
        </div>
      )}
    </div>
  )
}

function ResearchApp() {
  const { instance, accounts } = useMsal()
  const [activeTab, setActiveTab] = useState('research') // 'research' | 'history'

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

  return (
    <div id="center">
      <h1>Alpha - Stock Research</h1>

      <div className="tab-bar">
        <button
          className={activeTab === 'research' ? 'tab-btn tab-active' : 'tab-btn'}
          onClick={() => setActiveTab('research')}
        >
          New Research
        </button>
        <button
          className={activeTab === 'history' ? 'tab-btn tab-active' : 'tab-btn'}
          onClick={() => setActiveTab('history')}
        >
          History
        </button>
      </div>

      {activeTab === 'research' && <ResearchTab getAccessToken={getAccessToken} />}
      {activeTab === 'history' && <HistoryTab getAccessToken={getAccessToken} />}
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
