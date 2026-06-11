"""
Outcome tracking — the accountability layer.

Records every monthly recommendation with its entry price into an append-only
ledger, then scores how those picks have performed versus simply buying SPY at
the same time. This is what turns the advisor from "vibes" into something
measurable: you find out whether the factor-driven picks actually added value.

The scoring functions are pure (data in, numbers out) and unit-tested offline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from config import DATA_DIR

TRACKING_DIR = DATA_DIR / "tracking"
TRACKING_DIR.mkdir(parents=True, exist_ok=True)
LEDGER_PATH = TRACKING_DIR / "ledger.json"
PERFORMANCE_PATH = TRACKING_DIR / "performance.json"


# ── Ledger ───────────────────────────────────────────────────────────
def load_ledger(path: Path = LEDGER_PATH) -> list:
    p = Path(path)
    if not p.exists():
        return []
    try:
        return json.load(open(p))
    except Exception:  # noqa: BLE001
        return []


def save_ledger(ledger: list, path: Path = LEDGER_PATH) -> None:
    json.dump(ledger, open(path, "w"), indent=2)


def record_recommendations(
    recs: dict, prices: dict, month: str, entry_date: str, ledger: Optional[list] = None
) -> list:
    """
    Append this month's picks to the ledger with their entry prices. Idempotent
    per month: re-running replaces any prior entries for the same month, so a
    re-run never double-counts. Returns the updated ledger (caller saves it).
    """
    ledger = list(ledger if ledger is not None else load_ledger())
    ledger = [e for e in ledger if e.get("month") != month]  # replace same-month

    for a in recs.get("allocations", []):
        ticker = a.get("ticker")
        price = prices.get(ticker)
        if price is None:
            print(f"  ⚠ no entry price for {ticker}; not tracked")
            continue
        ledger.append({
            "month": month,
            "entry_date": entry_date,
            "ticker": ticker,
            "amount": int(a.get("amount", 0)),
            "entry_price": round(float(price), 2),
            "category": a.get("category", ""),
            "conviction": a.get("conviction", ""),
        })
    return ledger


# ── Pure scoring ─────────────────────────────────────────────────────
def position_return_pct(entry_price: float, current_price: Optional[float]) -> Optional[float]:
    """Percent return of a single position from entry to now."""
    if not entry_price or current_price is None:
        return None
    return round((current_price / entry_price - 1) * 100, 2)


def _weighted(entries: list, key: str) -> Optional[float]:
    """Amount-weighted average of `key` across entries that have it."""
    usable = [e for e in entries if e.get(key) is not None and e.get("amount")]
    total = sum(e["amount"] for e in usable)
    if total == 0:
        return None
    return round(sum(e["amount"] * e[key] for e in usable) / total, 2)


def score_positions(ledger: list, current_prices: dict, benchmark_by_date: dict) -> list:
    """Attach current price, return %, SPY benchmark %, and alpha to each entry."""
    scored = []
    for e in ledger:
        cur = current_prices.get(e["ticker"])
        ret = position_return_pct(e.get("entry_price"), cur)
        bench = benchmark_by_date.get(e.get("entry_date"))
        alpha = round(ret - bench, 2) if (ret is not None and bench is not None) else None
        scored.append({
            **e,
            "current_price": round(float(cur), 2) if cur is not None else None,
            "return_pct": ret,
            "benchmark_pct": bench,
            "alpha": alpha,
        })
    return scored


def aggregate_by_month(scored: list) -> list:
    """Roll positions up into per-month, amount-weighted performance."""
    months: dict[str, list] = {}
    for e in scored:
        months.setdefault(e["month"], []).append(e)

    out = []
    for month in sorted(months):
        entries = months[month]
        out.append({
            "month": month,
            "entry_date": entries[0]["entry_date"],
            "invested": sum(e["amount"] for e in entries),
            "positions": len(entries),
            "return_pct": _weighted(entries, "return_pct"),
            "benchmark_pct": _weighted(entries, "benchmark_pct"),
            "alpha": _weighted(entries, "alpha"),
        })
    return out


def overall(scored: list) -> dict:
    """Amount-weighted performance across every tracked position."""
    return {
        "invested": sum(e["amount"] for e in scored),
        "positions": len(scored),
        "return_pct": _weighted(scored, "return_pct"),
        "benchmark_pct": _weighted(scored, "benchmark_pct"),
        "alpha": _weighted(scored, "alpha"),
    }


# ── Benchmark (SPY) ──────────────────────────────────────────────────
def _naive_index(series: pd.Series) -> pd.Series:
    idx = series.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return pd.Series(series.values, index=pd.DatetimeIndex(idx).normalize())


def benchmark_returns(entry_dates: list, spy_series: pd.Series) -> dict:
    """
    For each unique entry date, SPY's % return from that date (or the nearest
    prior trading day) to the latest close. Pure given a price series.
    """
    s = _naive_index(spy_series.dropna())
    if s.empty:
        return {d: None for d in set(entry_dates)}
    current = float(s.iloc[-1])
    out = {}
    for d in set(entry_dates):
        prior = s.loc[: pd.Timestamp(d).normalize()]
        if prior.empty:
            out[d] = None
            continue
        entry = float(prior.iloc[-1])
        out[d] = round((current / entry - 1) * 100, 2) if entry else None
    return out


# ── Orchestrator ─────────────────────────────────────────────────────
def build_performance(ledger: list, current_prices: dict, spy_series: pd.Series) -> dict:
    """Assemble the full performance object (pure, given prices + SPY series)."""
    bench = benchmark_returns([e["entry_date"] for e in ledger], spy_series)
    scored = score_positions(ledger, current_prices, bench)
    return {
        "positions": scored,
        "by_month": aggregate_by_month(scored),
        "overall": overall(scored),
    }


def update_performance(
    current_prices: dict,
    ledger: Optional[list] = None,
    spy_symbol: str = "SPY",
    perf_path: Path = PERFORMANCE_PATH,
) -> dict:
    """Fetch SPY, score the ledger against it, and write performance.json."""
    import yfinance as yf

    ledger = ledger if ledger is not None else load_ledger()
    if not ledger:
        perf = {"positions": [], "by_month": [], "overall": {}}
        json.dump(perf, open(perf_path, "w"), indent=2)
        return perf

    try:
        spy_hist = yf.Ticker(spy_symbol).history(period="2y")
        spy_series = spy_hist["Close"] if not spy_hist.empty else pd.Series(dtype=float)
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠ could not fetch {spy_symbol} for benchmark: {e}")
        spy_series = pd.Series(dtype=float)

    perf = build_performance(ledger, current_prices, spy_series)
    json.dump(perf, open(perf_path, "w"), indent=2, default=str)
    print(f"  Updated track record: {perf['overall'].get('positions', 0)} positions tracked")
    return perf
