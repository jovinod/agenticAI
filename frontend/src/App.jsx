import { useState } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [tickerInput, setTickerInput] = useState('')
  const [tickers, setTickers] = useState([])
  const [error, setError] = useState('')
  const [status, setStatus] = useState('idle') // 'idle' | 'loading' | 'done'
  const [report, setReport] = useState(null)

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

    const response = await fetch(`${API_URL}/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tickers: parsed }),
    })
    const { job_id } = await response.json()

    pollStatus(job_id)
  }

  function pollStatus(jobId) {
    const interval = setInterval(async () => {
      const response = await fetch(`${API_URL}/research/${jobId}`)
      const data = await response.json()

      if (data.status === 'done') {
        clearInterval(interval)
        setReport(data.result)
        setStatus('done')
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
          <button onClick={handleReset}>New search</button>
        </div>
      )}
    </div>
  )
}

export default App
