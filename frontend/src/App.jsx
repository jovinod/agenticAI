import { useState } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Bounded polling: the frontend checks at most this many times, waiting
// this long between checks. Waiting must have a defined end -- the exact
// numbers are a temporary policy choice, not a load-bearing contract.
const MAX_POLL_ATTEMPTS = 20
const POLL_INTERVAL_MS = 500

function App() {
  const [tickerInput, setTickerInput] = useState('')
  const [tickers, setTickers] = useState([])
  const [error, setError] = useState('')
  const [status, setStatus] = useState('idle') // 'idle' | 'loading' | 'done'
  const [report, setReport] = useState(null)

  async function pollJob(jobId) {
    for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))

      let response
      try {
        response = await fetch(`${API_URL}/research/${jobId}`)
      } catch (err) {
        setError('Lost connection to the server while waiting for results.')
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
    setTickers(parsed)
    setStatus('loading')

    let response
    try {
      response = await fetch(`${API_URL}/research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers: parsed }),
      })
    } catch (err) {
      setError('Could not reach the server. Check your connection and try again.')
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
  }

  return (
    <div id="center">
      <h1>Stock Research Assistant</h1>

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
          <small>Job: {report.jobId}</small>
          <button onClick={handleReset}>New search</button>
        </div>
      )}
    </div>
  )
}

export default App
