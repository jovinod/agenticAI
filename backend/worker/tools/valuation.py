"""
Intrinsic value via historical P/E -- adapted from buynobuy's real "Rokda
framework" method (skills/fundamentals/valuation_extractor.py), with one
deliberate change: market-agnostic instead of hardcoding India's April-March
fiscal year. Each company's own reported fiscal-year-end dates (from
yfinance's income_stmt) are used directly, with price averaged over the
trailing 12 months ending at that date -- works the same way for a US
ticker (fiscal year ending September) or an Indian one (ending March).

Method, unchanged from the original:
  1. For each fiscal year with a known EPS, average the closing price over
     the trailing 12 months ending at that fiscal year's end date.
  2. Historical P/E for that year = average price / EPS.
  3. Intrinsic P/E = mean of all historical P/Es.
  4. P/E CAGR = compound growth of P/E from earliest to latest year.
  5. Best Case P/E = latest P/E x (1 + P/E CAGR). Worst Case P/E = minimum historical P/E.
  6. Intrinsic/Best/Worst Case Price = latest EPS x the corresponding P/E.
  7. Margin of safety: BUY if CMP is >20% below intrinsic price, WAIT if
     below but by less than 20%, OVERPRICED if CMP exceeds it.
"""
from datetime import datetime, timedelta


def compute_intrinsic_value(eps_history: dict, monthly_prices, current_price: float | None) -> dict:
    """
    eps_history: {"2025-09-30": 7.46, ...} -- from fetch_extended_fundamentals.
    monthly_prices: pandas Series, tz-naive, indexed by date -- same source.
    """
    valid_eps = {fy: eps for fy, eps in eps_history.items() if eps and eps > 0}
    if not valid_eps:
        return {"note": "No positive EPS history available -- cannot compute intrinsic value."}

    fy_avg_prices, historical_pe = {}, {}
    for fy_label, eps in valid_eps.items():
        fy_end = datetime.strptime(fy_label, "%Y-%m-%d")
        window_start = fy_end - timedelta(days=365)
        subset = monthly_prices[(monthly_prices.index >= window_start) & (monthly_prices.index <= fy_end)]
        if len(subset) < 3:  # need at least 3 months for a meaningful average, same bar as the original
            continue
        avg_price = round(float(subset.mean()), 2)
        fy_avg_prices[fy_label] = avg_price
        historical_pe[fy_label] = round(avg_price / eps, 2)

    if not historical_pe:
        return {"note": "Insufficient price history alongside EPS history -- cannot compute intrinsic value."}

    sorted_fy = sorted(historical_pe.keys())
    pe_values = list(historical_pe.values())

    intrinsic_pe = round(sum(pe_values) / len(pe_values), 2)
    worst_case_pe = round(min(pe_values), 2)

    pe_cagr = None
    if len(sorted_fy) >= 2:
        first_pe, last_pe = historical_pe[sorted_fy[0]], historical_pe[sorted_fy[-1]]
        n_years = len(sorted_fy) - 1
        if first_pe > 0 and last_pe > 0:
            pe_cagr = round((last_pe / first_pe) ** (1 / n_years) - 1, 4)

    latest_pe = historical_pe[sorted_fy[-1]]
    best_case_pe = round(latest_pe * (1 + pe_cagr), 2) if pe_cagr else latest_pe

    latest_eps = valid_eps[sorted_fy[-1]]
    intrinsic_price = round(latest_eps * intrinsic_pe, 2)
    best_case_price = round(latest_eps * best_case_pe, 2)
    worst_case_price = round(latest_eps * worst_case_pe, 2)

    margin_of_safety = "UNKNOWN"
    upside_pct = None
    if current_price:
        upside_pct = round((best_case_price - current_price) / current_price * 100, 1)
        if current_price <= intrinsic_price * 0.8:
            margin_of_safety = "BUY -- current price is >20% below intrinsic price"
        elif current_price <= intrinsic_price:
            margin_of_safety = "WAIT -- current price is below intrinsic price but by less than 20%"
        else:
            margin_of_safety = "OVERPRICED -- current price exceeds intrinsic price"

    return {
        "fy_avg_prices": fy_avg_prices,
        "historical_pe": historical_pe,
        "intrinsic_pe": intrinsic_pe,
        "pe_cagr_pct": round(pe_cagr * 100, 1) if pe_cagr else None,
        "best_case_pe": best_case_pe,
        "worst_case_pe": worst_case_pe,
        "latest_eps": latest_eps,
        "intrinsic_price": intrinsic_price,
        "best_case_price": best_case_price,
        "worst_case_price": worst_case_price,
        "current_price": current_price,
        "upside_pct": upside_pct,
        "margin_of_safety": margin_of_safety,
        "note": (
            f"Based on {len(historical_pe)} fiscal year(s) of historical P/E. "
            f"Intrinsic P/E {intrinsic_pe}x, Best Case P/E {best_case_pe}x, Worst Case P/E {worst_case_pe}x."
        ),
    }
