"""
Tests for outcome tracking (src/tracking.py) — ledger recording + scoring.
All offline with synthetic data.

Run with: python -m pytest tests/test_tracking.py -v
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import tracking as T


RECS = {
    "allocations": [
        {"ticker": "AAA", "amount": 600, "category": "Core", "conviction": "High"},
        {"ticker": "BBB", "amount": 400, "category": "Growth", "conviction": "Medium"},
    ]
}
PRICES = {"AAA": 100.0, "BBB": 50.0}


# ── Ledger recording ─────────────────────────────────────────────────
class TestLedger:
    def test_records_entries_with_prices(self):
        led = T.record_recommendations(RECS, PRICES, "2026-01", "2026-01-01", [])
        assert len(led) == 2
        aaa = next(e for e in led if e["ticker"] == "AAA")
        assert aaa["entry_price"] == 100.0
        assert aaa["amount"] == 600
        assert aaa["month"] == "2026-01"
        assert aaa["category"] == "Core"

    def test_idempotent_replace_same_month(self):
        led = T.record_recommendations(RECS, PRICES, "2026-01", "2026-01-01", [])
        # Re-running the same month replaces, not duplicates.
        led = T.record_recommendations(RECS, PRICES, "2026-01", "2026-01-01", led)
        assert len([e for e in led if e["month"] == "2026-01"]) == 2

    def test_different_month_appends(self):
        led = T.record_recommendations(RECS, PRICES, "2026-01", "2026-01-01", [])
        led = T.record_recommendations(RECS, PRICES, "2026-02", "2026-02-01", led)
        assert {e["month"] for e in led} == {"2026-01", "2026-02"}
        assert len(led) == 4

    def test_missing_price_is_skipped(self):
        led = T.record_recommendations(RECS, {"AAA": 100.0}, "2026-01", "2026-01-01", [])
        assert [e["ticker"] for e in led] == ["AAA"]  # BBB had no price


# ── Scoring ──────────────────────────────────────────────────────────
class TestScoring:
    def test_position_return(self):
        assert T.position_return_pct(100, 120) == 20.0
        assert T.position_return_pct(100, 80) == -20.0
        assert T.position_return_pct(100, None) is None
        assert T.position_return_pct(0, 120) is None

    def test_score_positions_alpha(self):
        ledger = [{"month": "2026-01", "entry_date": "2026-01-01", "ticker": "AAA",
                   "amount": 600, "entry_price": 100}]
        scored = T.score_positions(ledger, {"AAA": 120}, {"2026-01-01": 10.0})
        s = scored[0]
        assert s["return_pct"] == 20.0
        assert s["benchmark_pct"] == 10.0
        assert s["alpha"] == 10.0          # beat SPY by 10pts
        assert s["current_price"] == 120

    def test_missing_current_price_nulls_out(self):
        ledger = [{"month": "2026-01", "entry_date": "2026-01-01", "ticker": "AAA",
                   "amount": 600, "entry_price": 100}]
        s = T.score_positions(ledger, {}, {"2026-01-01": 10.0})[0]
        assert s["return_pct"] is None and s["alpha"] is None

    def test_aggregate_by_month_is_amount_weighted(self):
        scored = [
            {"month": "2026-01", "entry_date": "2026-01-01", "amount": 600, "return_pct": 20.0,
             "benchmark_pct": 10.0, "alpha": 10.0},
            {"month": "2026-01", "entry_date": "2026-01-01", "amount": 400, "return_pct": -10.0,
             "benchmark_pct": 10.0, "alpha": -20.0},
        ]
        agg = T.aggregate_by_month(scored)[0]
        # (600*20 + 400*-10) / 1000 = 8.0
        assert agg["return_pct"] == 8.0
        assert agg["invested"] == 1000
        assert agg["positions"] == 2

    def test_overall_amount_weighted(self):
        scored = [
            {"month": "2026-01", "amount": 600, "return_pct": 20.0, "benchmark_pct": 10.0, "alpha": 10.0},
            {"month": "2026-02", "amount": 400, "return_pct": -10.0, "benchmark_pct": 5.0, "alpha": -15.0},
        ]
        o = T.overall(scored)
        assert o["invested"] == 1000
        assert o["return_pct"] == 8.0           # (600*20 + 400*-10)/1000
        assert o["positions"] == 2

    def test_weighted_skips_none(self):
        scored = [
            {"amount": 500, "return_pct": 10.0},
            {"amount": 500, "return_pct": None},   # excluded from the weighting
        ]
        assert T._weighted(scored, "return_pct") == 10.0


# ── Benchmark (SPY) ──────────────────────────────────────────────────
class TestBenchmark:
    def test_benchmark_returns_from_entry_date(self):
        spy = pd.Series([100.0, 110.0, 120.0],
                        index=pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"]))
        b = T.benchmark_returns(["2026-01-01", "2026-02-01"], spy)
        assert b["2026-01-01"] == 20.0          # 100 -> 120
        assert b["2026-02-01"] == pytest.approx(9.09, abs=0.01)  # 110 -> 120

    def test_uses_nearest_prior_trading_day(self):
        spy = pd.Series([100.0, 130.0],
                        index=pd.to_datetime(["2026-01-02", "2026-03-01"]))
        # Entry on a date before any data -> nearest prior is none -> None
        b = T.benchmark_returns(["2026-01-01"], spy)
        assert b["2026-01-01"] is None
        # Entry after first point -> uses that point
        b2 = T.benchmark_returns(["2026-02-15"], spy)
        assert b2["2026-02-15"] == 30.0

    def test_empty_series_returns_none(self):
        b = T.benchmark_returns(["2026-01-01"], pd.Series(dtype=float))
        assert b["2026-01-01"] is None


# ── End-to-end (pure) ────────────────────────────────────────────────
class TestBuildPerformance:
    def test_build_performance_end_to_end(self):
        ledger = [
            {"month": "2026-01", "entry_date": "2026-01-01", "ticker": "AAA", "amount": 600, "entry_price": 100},
            {"month": "2026-01", "entry_date": "2026-01-01", "ticker": "BBB", "amount": 400, "entry_price": 50},
        ]
        spy = pd.Series([400.0, 440.0], index=pd.to_datetime(["2026-01-01", "2026-06-01"]))  # +10%
        perf = T.build_performance(ledger, {"AAA": 130, "BBB": 50}, spy)
        assert len(perf["positions"]) == 2
        assert perf["overall"]["invested"] == 1000
        # AAA +30%, BBB +0%, weighted = (600*30 + 400*0)/1000 = 18.0
        assert perf["overall"]["return_pct"] == 18.0
        assert perf["overall"]["benchmark_pct"] == 10.0
        assert perf["overall"]["alpha"] == 8.0
