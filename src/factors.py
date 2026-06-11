"""
Factor engine for the AI Investment Advisor.

Computes technical + fundamental factors for every ticker, ranks them
cross-sectionally (percentiles within the universe), and rolls them into
composite Value / Momentum / Quality / Growth / Low-Vol scores.

Design principle: Python computes, Claude reasons. The LLM is bad at arithmetic
over dozens of tickers but good at reasoning over a clean ranked scorecard.

The math functions are pure (history DataFrame + info dict in, numbers out) so
they can be unit-tested offline without network access. `compute_factors()` is
the orchestrator that fetches data and assembles the full scorecard.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

# Trading-day windows (approximate calendar periods)
TD_1M = 21
TD_3M = 63
TD_6M = 126
TD_12M = 252

# ── Composite factor definitions ─────────────────────────────────────
# Each composite is a list of (raw_factor_key, direction) pairs.
# direction = +1 means "higher is better"; -1 means "lower is better"
# (e.g. a low P/E is good for Value, so trailing_pe has direction -1).
COMPOSITES = {
    "value": [
        ("trailing_pe", -1),
        ("forward_pe", -1),
        ("price_to_sales", -1),
        ("price_to_book", -1),
        ("ev_to_ebitda", -1),
        ("peg_ratio", -1),
    ],
    "momentum": [
        ("momentum_12_1", +1),
        ("ret_3m", +1),
        ("ret_6m", +1),
        ("price_vs_sma200", +1),
    ],
    "quality": [
        ("gross_margin", +1),
        ("operating_margin", +1),
        ("return_on_equity", +1),
        ("return_on_assets", +1),
        ("debt_to_equity", -1),
    ],
    "growth": [
        ("revenue_growth", +1),
        ("earnings_growth", +1),
    ],
    "low_vol": [
        ("volatility", -1),
        ("beta", -1),
        ("max_drawdown", +1),  # max_drawdown is negative; closer to 0 is better
    ],
}


# ── Technical factors (pure functions over price history) ────────────
def _safe_pct_change(series: pd.Series, periods: int) -> Optional[float]:
    """Return % change over `periods` rows, or None if insufficient history."""
    if len(series) <= periods:
        return None
    past = series.iloc[-(periods + 1)]
    now = series.iloc[-1]
    if past == 0 or pd.isna(past) or pd.isna(now):
        return None
    return float((now / past - 1.0) * 100.0)


def trailing_return(close: pd.Series, periods: int) -> Optional[float]:
    """Total return % over the trailing N trading days."""
    return _safe_pct_change(close, periods)


def momentum_12_1(close: pd.Series) -> Optional[float]:
    """
    Classic 12-1 momentum factor: 12-month return excluding the most recent
    month (skips short-term reversal). = price[-21] / price[-252] - 1.
    """
    if len(close) <= TD_12M:
        return None
    p_recent = close.iloc[-TD_1M]
    p_old = close.iloc[-TD_12M]
    if p_old == 0 or pd.isna(p_old) or pd.isna(p_recent):
        return None
    return float((p_recent / p_old - 1.0) * 100.0)


def sma(close: pd.Series, window: int) -> Optional[float]:
    """Simple moving average of the last `window` closes."""
    if len(close) < window:
        return None
    return float(close.iloc[-window:].mean())


def price_vs_sma(close: pd.Series, window: int) -> Optional[float]:
    """Current price as % above/below its `window`-day SMA."""
    avg = sma(close, window)
    if avg is None or avg == 0:
        return None
    return float((close.iloc[-1] / avg - 1.0) * 100.0)


def rsi(close: pd.Series, window: int = 14) -> Optional[float]:
    """Wilder's RSI over `window` periods (0-100)."""
    if len(close) <= window:
        return None
    delta = close.diff().dropna()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    # Wilder's smoothing via exponential weighting
    avg_gain = gains.ewm(alpha=1 / window, min_periods=window).mean().iloc[-1]
    avg_loss = losses.ewm(alpha=1 / window, min_periods=window).mean().iloc[-1]
    if pd.isna(avg_gain) or pd.isna(avg_loss):
        return None
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def annualized_volatility(close: pd.Series) -> Optional[float]:
    """Annualized stdev of daily returns, as a percentage."""
    if len(close) < 2:
        return None
    daily = close.pct_change().dropna()
    if daily.empty:
        return None
    return float(daily.std() * math.sqrt(252) * 100.0)


def _naive_daily_returns(series: pd.Series) -> pd.Series:
    """
    Daily returns indexed by tz-naive calendar date, so series from different
    sources (crypto is UTC, equities are exchange-local) align by date instead
    of by exact timestamp.
    """
    returns = series.pct_change().dropna()
    idx = returns.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return pd.Series(returns.values, index=pd.DatetimeIndex(idx).normalize())


def beta(close: pd.Series, benchmark_close: pd.Series) -> Optional[float]:
    """Beta of the asset vs. a benchmark, over the overlapping window."""
    if len(close) < 2 or len(benchmark_close) < 2:
        return None
    a = _naive_daily_returns(close)
    b = _naive_daily_returns(benchmark_close)
    joined = pd.concat([a, b], axis=1, join="inner").dropna()
    if len(joined) < 20:
        return None
    var = joined.iloc[:, 1].var()
    if var == 0:
        return None
    cov = joined.iloc[:, 0].cov(joined.iloc[:, 1])
    return float(cov / var)


def max_drawdown(close: pd.Series) -> Optional[float]:
    """Worst peak-to-trough decline over the series, as a (negative) %."""
    if len(close) < 2:
        return None
    running_max = close.cummax()
    drawdown = close / running_max - 1.0
    return float(drawdown.min() * 100.0)


def pct_from_extreme(price: float, extreme: Optional[float]) -> Optional[float]:
    """Current price as % distance from a 52w high/low level."""
    if extreme is None or extreme == 0 or pd.isna(extreme):
        return None
    return float((price / extreme - 1.0) * 100.0)


def compute_technical_factors(
    close: pd.Series, info: dict, benchmark_close: Optional[pd.Series]
) -> dict:
    """
    All price-derived factors for one ticker. Expects ~2y of history so that
    12-1 momentum (needs 252+ days) computes. Volatility, beta, and max
    drawdown are measured over the trailing ~1 year for stable, comparable
    risk metrics.
    """
    price = float(close.iloc[-1])
    one_year = close.tail(TD_12M)
    bench_year = benchmark_close.tail(TD_12M) if benchmark_close is not None else None
    return {
        "ret_1w": trailing_return(close, 5),
        "ret_1m": trailing_return(close, TD_1M),
        "ret_3m": trailing_return(close, TD_3M),
        "ret_6m": trailing_return(close, TD_6M),
        "ret_12m": trailing_return(close, TD_12M),
        "momentum_12_1": momentum_12_1(close),
        "price_vs_sma50": price_vs_sma(close, 50),
        "price_vs_sma200": price_vs_sma(close, 200),
        "rsi_14": rsi(close, 14),
        "volatility": annualized_volatility(one_year),
        "beta": beta(one_year, bench_year) if bench_year is not None else None,
        "max_drawdown": max_drawdown(one_year),
        "pct_from_52w_high": pct_from_extreme(price, info.get("fiftyTwoWeekHigh")),
        "pct_from_52w_low": pct_from_extreme(price, info.get("fiftyTwoWeekLow")),
    }


# ── Fundamental factors (pure function over .info dict) ──────────────
def _num(value) -> Optional[float]:
    """Coerce to float, treating None/NaN/non-numeric as missing."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def compute_fundamental_factors(info: dict) -> dict:
    """All fundamentals for one ticker, normalized to floats or None."""
    target = _num(info.get("targetMeanPrice"))
    current = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
    target_upside = None
    if target is not None and current not in (None, 0):
        target_upside = (target / current - 1.0) * 100.0

    # yfinance reports margins/growth/yield as fractions (0.25 == 25%);
    # scale to percentages for readability and consistent ranking.
    def pct(key):
        v = _num(info.get(key))
        return v * 100.0 if v is not None else None

    return {
        "trailing_pe": _num(info.get("trailingPE")),
        "forward_pe": _num(info.get("forwardPE")),
        "peg_ratio": _num(info.get("pegRatio") or info.get("trailingPegRatio")),
        "price_to_sales": _num(info.get("priceToSalesTrailing12Months")),
        "price_to_book": _num(info.get("priceToBook")),
        "ev_to_ebitda": _num(info.get("enterpriseToEbitda")),
        "gross_margin": pct("grossMargins"),
        "operating_margin": pct("operatingMargins"),
        "profit_margin": pct("profitMargins"),
        "return_on_equity": pct("returnOnEquity"),
        "return_on_assets": pct("returnOnAssets"),
        "revenue_growth": pct("revenueGrowth"),
        "earnings_growth": pct("earningsGrowth") if _num(info.get("earningsGrowth")) is not None else pct("earningsQuarterlyGrowth"),
        "debt_to_equity": _num(info.get("debtToEquity")),
        "current_ratio": _num(info.get("currentRatio")),
        "free_cash_flow": _num(info.get("freeCashflow")),
        "dividend_yield": pct("dividendYield"),
        "target_upside": target_upside,
        "analyst_rating": _num(info.get("recommendationMean")),
        "num_analysts": _num(info.get("numberOfAnalystOpinions")),
    }


# ── Cross-sectional ranking + composites ─────────────────────────────
def percentile_ranks(values: dict, direction: int = +1) -> dict:
    """
    Convert {ticker: value} into {ticker: percentile 0-100}, ranking only
    tickers that have a value. direction=-1 inverts (low value -> high rank).
    Tickers with None are omitted from the result.
    """
    present = {t: v for t, v in values.items() if v is not None}
    if len(present) < 2:
        return {t: 50.0 for t in present}
    s = pd.Series(present, dtype="float64")
    if direction < 0:
        s = -s
    ranked = s.rank(pct=True) * 100.0
    return {t: float(round(r, 1)) for t, r in ranked.items()}


def _zscores(values: dict, direction: int) -> dict:
    """{ticker: value} -> {ticker: signed z-score}, omitting missing."""
    present = {t: v for t, v in values.items() if v is not None}
    if len(present) < 2:
        return {}
    s = pd.Series(present, dtype="float64")
    std = s.std()
    if std == 0 or pd.isna(std):
        return {t: 0.0 for t in present}
    z = (s - s.mean()) / std
    return {t: float(z[t] * direction) for t in present}


def compute_composites(per_ticker_factors: dict) -> dict:
    """
    Build composite scores for each ticker. Returns
    {ticker: {composite_name: percentile_0_100}}.

    Method: z-score each component within the universe, sign-adjust by
    direction, average the available components, then percentile-rank the
    averaged scores so the output is an interpretable 0-100 within the universe.
    """
    tickers = list(per_ticker_factors.keys())
    result = {t: {} for t in tickers}

    for comp_name, components in COMPOSITES.items():
        # Collect z-scores per component
        component_z = []
        for factor_key, direction in components:
            col = {t: per_ticker_factors[t].get(factor_key) for t in tickers}
            z = _zscores(col, direction)
            if z:
                component_z.append(z)

        if not component_z:
            continue

        # Average available z-scores per ticker (ignoring components it lacks)
        avg_z = {}
        for t in tickers:
            vals = [z[t] for z in component_z if t in z]
            if vals:
                avg_z[t] = sum(vals) / len(vals)

        # Percentile-rank the averaged composite (higher avg_z = better = high pct)
        ranked = percentile_ranks(avg_z, direction=+1)
        for t, pct in ranked.items():
            result[t][comp_name] = pct

    return result


# ── Orchestrator ─────────────────────────────────────────────────────
def compute_factors(tickers: list[str], benchmark: str = "SPY") -> dict:
    """
    Fetch ~1y of history + fundamentals for every ticker and assemble the
    full factor scorecard.

    Returns:
        {
          "ticker": {
            "price": float,
            "technical": {...}, "fundamental": {...},
            "ranks": {factor: percentile}, "composites": {value/momentum/...},
          },
          ...
        }
    """
    import yfinance as yf

    # Benchmark history for beta (2y so 12-1 momentum has enough history)
    benchmark_close = None
    try:
        bench_hist = yf.Ticker(benchmark).history(period="2y")
        if not bench_hist.empty:
            benchmark_close = bench_hist["Close"]
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠ Could not fetch benchmark {benchmark}: {e}")

    per_ticker = {}
    print(f"Computing factors for {len(tickers)} tickers...")
    for symbol in tickers:
        try:
            tk = yf.Ticker(symbol)
            hist = tk.history(period="2y")
            if hist.empty:
                print(f"  ⚠ No history for {symbol}, skipping")
                continue
            info = tk.info or {}
            close = hist["Close"].dropna()
            if close.empty:
                continue

            technical = compute_technical_factors(close, info, benchmark_close)
            fundamental = compute_fundamental_factors(info)
            per_ticker[symbol] = {
                "price": round(float(close.iloc[-1]), 2),
                "sector": info.get("sector", "ETF/Fund"),
                "technical": technical,
                "fundamental": fundamental,
            }
            print(f"  ✓ {symbol}")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {symbol}: {e}")
            continue

    if not per_ticker:
        return {}

    # Flatten technical + fundamental into one factor namespace per ticker
    flat = {
        t: {**d["technical"], **d["fundamental"]} for t, d in per_ticker.items()
    }

    # Per-factor percentile ranks across the universe
    all_factor_keys = set()
    for d in flat.values():
        all_factor_keys.update(d.keys())

    # Direction lookup from composite definitions (default +1 if unspecified)
    direction_for = {}
    for components in COMPOSITES.values():
        for key, direction in components:
            direction_for[key] = direction

    ranks_by_factor = {}
    for key in all_factor_keys:
        col = {t: flat[t].get(key) for t in flat}
        ranks_by_factor[key] = percentile_ranks(col, direction_for.get(key, +1))

    # Composites
    composites = compute_composites(flat)

    # Assemble final scorecard
    for t in per_ticker:
        per_ticker[t]["ranks"] = {
            key: ranks_by_factor[key][t]
            for key in all_factor_keys
            if t in ranks_by_factor.get(key, {})
        }
        per_ticker[t]["composites"] = composites.get(t, {})

    return per_ticker


# ── Prompt formatting ────────────────────────────────────────────────
def format_factor_scorecard(factor_data: dict, watchlist: dict) -> str:
    """
    Render the factor scorecard as a compact, readable table grouped by
    category, for inclusion in an LLM prompt. Shows composite percentiles
    (the headline signal) plus a few key raw values for context.
    """
    if not factor_data:
        return "No factor data available."

    lines = []
    comp_order = ["value", "momentum", "quality", "growth", "low_vol"]

    for category, tickers in watchlist.items():
        present = [t for t in tickers if t in factor_data]
        if not present:
            continue
        lines.append(f"\n## {category.replace('_', ' ').title()}")
        header = (
            f"{'Ticker':<10}{'Price':>9}  "
            + "".join(f"{c[:4].title():>6}" for c in comp_order)
            + f"{'12-1Mom':>9}{'RSI':>6}{'Vol%':>7}{'fwPE':>7}{'52wH%':>7}"
        )
        lines.append(header)
        lines.append("-" * len(header))
        for t in present:
            d = factor_data[t]
            comps = d.get("composites", {})
            tech = d.get("technical", {})
            fund = d.get("fundamental", {})

            def fmt(v, suffix="", width=6, decimals=0):
                if v is None:
                    return f"{'—':>{width}}"
                return f"{v:>{width}.{decimals}f}{suffix}"

            comp_cells = "".join(
                fmt(comps.get(c), width=6, decimals=0) for c in comp_order
            )
            row = (
                f"{t:<10}{d['price']:>9.2f}  "
                + comp_cells
                + fmt(tech.get("momentum_12_1"), "%", width=8, decimals=1)
                + fmt(tech.get("rsi_14"), width=6, decimals=0)
                + fmt(tech.get("volatility"), width=7, decimals=0)
                + fmt(fund.get("forward_pe"), width=7, decimals=1)
                + fmt(tech.get("pct_from_52w_high"), "%", width=6, decimals=0)
            )
            lines.append(row)

    lines.append(
        "\nComposite columns are PERCENTILE RANKS within this universe (0-100, "
        "higher = stronger on that factor). Value=cheap, Momentum=trending up, "
        "Quality=profitable/low-debt, Growth=revenue/earnings growth, "
        "Low_Vol=stable/low-beta. Raw columns: 12-1Mom=12-month momentum ex last "
        "month, RSI=14d (>70 overbought, <30 oversold), Vol%=annualized volatility, "
        "fwPE=forward P/E, 52wH%=distance from 52-week high. '—' = data unavailable "
        "(common for crypto/ETFs)."
    )
    return "\n".join(lines)
