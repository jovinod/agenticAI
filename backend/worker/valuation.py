from typing import Any

MARGIN_OF_SAFETY = 0.8


def compute_intrinsic_value(
    eps_history: dict[str, float],
    monthly_prices: dict[str, float] | None,
    current_price: float | None,
) -> dict[str, Any]:
    """Historical price-to-earnings valuation, not a model-generated
    target. For each fiscal year with positive EPS, average trailing
    monthly prices give that year's P/E; the mean of those multiples is
    the intrinsic multiple applied to the latest EPS.

    A zero-argument closure over one captured dataset makes this call
    idempotent: the model can request it any number of times and always
    receive the same result, because it supplies no inputs of its own.
    """
    positive_years = {
        year: eps for year, eps in eps_history.items() if eps and eps > 0
    }

    if not positive_years or not monthly_prices or not current_price:
        return {
            "intrinsic_price": None,
            "best_case_price": None,
            "worst_case_price": None,
            "label": "UNKNOWN",
        }

    pe_values = []
    for year, eps in sorted(positive_years.items()):
        prices_for_year = [
            price for key, price in monthly_prices.items() if key.startswith(year)
        ]
        if not prices_for_year:
            continue
        average_price = sum(prices_for_year) / len(prices_for_year)
        pe_values.append(average_price / eps)

    if not pe_values:
        return {
            "intrinsic_price": None,
            "best_case_price": None,
            "worst_case_price": None,
            "label": "UNKNOWN",
        }

    latest_year = sorted(positive_years.keys())[-1]
    latest_eps = positive_years[latest_year]

    intrinsic_pe = sum(pe_values) / len(pe_values)
    best_case_pe = max(pe_values)
    worst_case_pe = min(pe_values)

    intrinsic_price = latest_eps * intrinsic_pe
    best_case_price = latest_eps * best_case_pe
    worst_case_price = latest_eps * worst_case_pe

    if current_price <= intrinsic_price * MARGIN_OF_SAFETY:
        label = "BUY"
    elif current_price <= intrinsic_price:
        label = "WAIT"
    else:
        label = "OVERPRICED"

    return {
        "intrinsic_price": intrinsic_price,
        "best_case_price": best_case_price,
        "worst_case_price": worst_case_price,
        "label": label,
    }
