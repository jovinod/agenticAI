import { useState } from 'react'
import './App.css'

function App() {
  const [tickerInput, setTickerInput] = useState('')
  const [tickers, setTickers] = useState([])
  const [error, setError] = useState('')
  const [status, setStatus] = useState('idle') // 'idle' | 'loading' | 'done'
  const [report, setReport] = useState(null)

  function handleSubmit() {
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

    const jobId = crypto.randomUUID()
    setTimeout(() => {
      setReport({
        jobId,
        summary: parsed.map((t) => `${t}: looks solid, no major red flags.`),
      })
      setStatus('done')
    }, 2000)
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
