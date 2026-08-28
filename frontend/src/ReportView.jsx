// Renders the structured Decision/Devil's Advocate output when present
// (report.decisions[ticker]) -- falls back to the plain summary lines for a
// ticker that doesn't have it (a cached result from before this feature, or
// a ticker whose job failed before reaching Decision).

function TickerReport({ ticker, decision }) {
  const rec = (decision.recommendation || '').toLowerCase()
  const iv = decision.intrinsic_value || {}
  const devil = decision.devil_advocate || {}
  const hardStops = decision.hard_stops_triggered || []
  const reasons = devil.reasons || []

  return (
    <div className="ticker-report">
      <h2 className="ticker-report-heading">{ticker}</h2>

      <div className={`rec-banner rec-${rec || 'unknown'}`}>
        <div className="rec-badge">{decision.recommendation || 'N/A'}</div>
        <div className="rec-detail">
          {decision.overall_score != null && (
            <div className="rec-score">Overall Score: {decision.overall_score}/10</div>
          )}
          <div className="rec-summary">{decision.final_report}</div>
        </div>
      </div>

      {hardStops.length > 0 && (
        <div className="hard-stop">
          <h3>Hard Stops Triggered</h3>
          <ul>
            {hardStops.map((stop) => <li key={stop}>{stop}</li>)}
          </ul>
        </div>
      )}

      {iv.intrinsic_price != null && (
        <div className="price-snapshot">
          <div className="price-card cmp-card">
            <div className="pc-label">Current Price</div>
            <div className="pc-value">{iv.current_price}</div>
          </div>
          <div className={`price-card ${(iv.margin_of_safety || '').startsWith('OVERPRICED') ? 'overpriced' : 'undervalued'}`}>
            <div className="pc-label">Intrinsic Value</div>
            <div className="pc-value">{iv.intrinsic_price}</div>
            <div className="pc-sub">{iv.margin_of_safety}</div>
          </div>
          <div className="price-card">
            <div className="pc-label">Best Case</div>
            <div className="pc-value">{iv.best_case_price}</div>
          </div>
          <div className="price-card">
            <div className="pc-label">Worst Case</div>
            <div className="pc-value">{iv.worst_case_price}</div>
          </div>
        </div>
      )}

      {devil.summary && (
        <div className="devil-section">
          <div className="devil-header">
            <span className="devil-icon" aria-hidden="true">!</span>
            <h3>
              Devil's Advocate
              {devil.bear_score != null ? ` — Bear score ${devil.bear_score}/10` : ''}
            </h3>
          </div>
          <div className="devil-summary">{devil.summary}</div>
          {reasons.length > 0 && (
            <div className="devil-reasons">
              {reasons.map((reason, i) => (
                <div className="devil-reason" key={i}>
                  <strong className="devil-heading">{reason.heading}</strong>
                  <p className="devil-detail">{reason.detail}</p>
                </div>
              ))}
            </div>
          )}
          {devil.closing_fact && <div className="devil-closing">{devil.closing_fact}</div>}
        </div>
      )}
    </div>
  )
}

export default function ReportView({ report }) {
  return (
    <div className="report-view">
      {report.tickers.map((ticker) => {
        const decision = report.decisions?.[ticker]
        if (!decision) {
          const lines = report.summary.filter((line) => line.startsWith(`${ticker}:`))
          return (
            <div className="ticker-report" key={ticker}>
              <h2 className="ticker-report-heading">{ticker}</h2>
              <ul className="fallback-summary">
                {lines.map((line) => <li key={line}>{line}</li>)}
              </ul>
            </div>
          )
        }
        return <TickerReport key={ticker} ticker={ticker} decision={decision} />
      })}
    </div>
  )
}
