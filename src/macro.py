"""
Macro regime + cross-asset correlation context.

Two layers that the factor scorecard alone can't capture:
  1. Macro regime — Treasury yields, the yield curve, volatility (VIX), and the
     dollar. Tells the model whether it's a risk-on or risk-off environment.
  2. Correlations — how tightly the universe's assets move together, so the
     monthly recommendation can avoid stacking correlated names (real
     diversification, not just "different tickers").

The format_* functions are pure (dict in, string out) and unit-tested offline.
The compute_* functions fetch from yfinance.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from config import MACRO_TICKERS


# ── Macro regime ─────────────────────────────────────────────────────
def _latest_and_change(close: pd.Series) -> Optional[dict]:
    """Latest value + absolute change over the supplied window."""
    if close is None or len(close) == 0:
        return None
    latest = float(close.iloc[-1])
    first = float(close.iloc[0])
    return {"value": round(latest, 2), "change": round(latest - first, 2)}


def compute_macro_context(period: str = "1mo") -> dict:
    """Fetch the macro regime indicators and the 10Y-3M yield curve."""
    import yfinance as yf

    out = {}
    for key, symbol in MACRO_TICKERS.items():
        try:
            hist = yf.Ticker(symbol).history(period=period)
            out[key] = _latest_and_change(hist["Close"].dropna()) if not hist.empty else None
        except Exception as e:  # noqa: BLE001
            print(f"  ⚠ macro {symbol}: {e}")
            out[key] = None

    ten, three = out.get("ten_year"), out.get("three_month")
    out["yield_curve_10y_3m"] = (
        round(ten["value"] - three["value"], 2) if ten and three else None
    )
    return out


def _vix_regime(level: float) -> str:
    if level < 15:
        return "calm"
    if level < 20:
        return "normal"
    if level < 30:
        return "elevated"
    return "high fear"


def format_macro_summary(m: dict) -> str:
    """Render the macro context as a prompt-friendly block."""
    if not m:
        return "Macro data unavailable."

    def line(d: Optional[dict], name: str, unit: str = "") -> str:
        if not d:
            return f"{name}: n/a"
        arrow = "▲" if d["change"] > 0 else ("▼" if d["change"] < 0 else "→")
        return f"{name}: {d['value']}{unit} ({arrow} {abs(d['change'])}{unit} MoM)"

    lines = ["## Macro Regime"]
    lines.append(line(m.get("ten_year"), "10Y Treasury yield", "%"))
    lines.append(line(m.get("three_month"), "3M T-bill yield", "%"))

    curve = m.get("yield_curve_10y_3m")
    if curve is not None:
        state = "INVERTED (historic recession signal)" if curve < 0 else "normal (upward sloping)"
        lines.append(f"Yield curve (10Y-3M): {curve:+.2f} pts — {state}")

    vix = m.get("vix")
    lines.append(line(vix, "VIX (volatility)"))
    if vix:
        lines.append(f"  → volatility regime: {_vix_regime(vix['value'])}")

    lines.append(line(m.get("dollar"), "US Dollar Index (DXY)"))
    return "\n".join(lines)


# ── Cross-asset correlations ─────────────────────────────────────────
def _naive_close(close: pd.Series) -> pd.Series:
    """Close series re-indexed to tz-naive calendar dates for cross-asset alignment."""
    idx = close.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return pd.Series(close.values, index=pd.DatetimeIndex(idx).normalize())


def correlation_summary_from_closes(closes: dict, top_n: int = 8) -> dict:
    """
    Build a correlation summary from {ticker: close_series}.
    Pure (no network) so it can be unit-tested.
    Returns {avg_corr: {ticker: x}, top_pairs: [(a, b, corr), ...]}.
    """
    aligned = {t: _naive_close(c) for t, c in closes.items() if c is not None and len(c) > 1}
    if len(aligned) < 2:
        return {}

    returns = pd.DataFrame(aligned).pct_change().dropna(how="all")
    corr = returns.corr()

    avg_corr = {}
    for t in corr.columns:
        others = corr[t].drop(labels=[t]).dropna()
        if len(others):
            avg_corr[t] = round(float(others.mean()), 2)

    pairs = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            v = corr.iloc[i, j]
            if pd.notna(v):
                pairs.append((cols[i], cols[j], round(float(v), 2)))
    pairs.sort(key=lambda x: -x[2])

    return {"avg_corr": avg_corr, "top_pairs": pairs[:top_n]}


def compute_correlation_summary(tickers: list[str], period: str = "1y", top_n: int = 8) -> dict:
    """Fetch close-only history (lighter than full factor data) and summarize correlations."""
    import yfinance as yf

    closes = {}
    for symbol in tickers:
        try:
            hist = yf.Ticker(symbol).history(period=period)
            if not hist.empty:
                closes[symbol] = hist["Close"].dropna()
        except Exception:  # noqa: BLE001
            continue
    return correlation_summary_from_closes(closes, top_n=top_n)


def format_correlation_summary(c: dict) -> str:
    """Render the correlation summary as a prompt-friendly block."""
    if not c or not c.get("top_pairs"):
        return ""

    lines = ["## Cross-Asset Correlations (1y daily returns)"]
    lines.append("Most-correlated pairs — avoid holding several of these together, they move as one:")
    for a, b, v in c["top_pairs"]:
        lines.append(f"  {a} ↔ {b}: {v:+.2f}")

    avg = c.get("avg_corr", {})
    if avg:
        crowded = sorted(avg.items(), key=lambda x: -x[1])[:5]
        lines.append("Least-diversifying names (highest average correlation to the universe):")
        for t, v in crowded:
            lines.append(f"  {t}: {v:+.2f}")
    return "\n".join(lines)
