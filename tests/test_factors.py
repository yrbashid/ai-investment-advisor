"""
Tests for the factor engine (src/factors.py).

These exercise the pure math functions with synthetic data — no network —
so they run fast and deterministically.

Run with: python -m pytest tests/test_factors.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import factors as F


# ── Fixtures: synthetic price series ─────────────────────────────────
N = 300
IDX = pd.date_range("2025-01-01", periods=N, freq="D")
UPTREND = pd.Series(np.linspace(100, 200, N), index=IDX)
DOWNTREND = pd.Series(np.linspace(200, 100, N), index=IDX)
FLAT = pd.Series(np.full(N, 100.0), index=IDX)


def _noisy(seed=0, vol=0.02):
    rng = np.random.default_rng(seed)
    return pd.Series(100 * np.cumprod(1 + rng.normal(0, vol, N)), index=IDX)


# ── Technical factors ────────────────────────────────────────────────
class TestTechnical:
    def test_trailing_return_positive_uptrend(self):
        assert F.trailing_return(UPTREND, F.TD_12M) > 40

    def test_trailing_return_insufficient_history(self):
        assert F.trailing_return(UPTREND.iloc[:10], F.TD_12M) is None

    def test_momentum_sign(self):
        assert F.momentum_12_1(UPTREND) > 0
        assert F.momentum_12_1(DOWNTREND) < 0

    def test_price_vs_sma(self):
        assert F.price_vs_sma(UPTREND, 200) > 0
        assert F.price_vs_sma(DOWNTREND, 200) < 0
        assert F.price_vs_sma(FLAT, 50) == pytest.approx(0.0, abs=1e-9)

    def test_rsi_bounds_and_sign(self):
        assert F.rsi(UPTREND) > 70
        assert F.rsi(DOWNTREND) < 30

    def test_volatility(self):
        assert F.annualized_volatility(FLAT) == pytest.approx(0.0, abs=1e-9)
        assert F.annualized_volatility(_noisy()) > 10

    def test_beta_identical_is_one(self):
        s = _noisy()
        assert F.beta(s, s) == pytest.approx(1.0, abs=1e-6)

    def test_max_drawdown(self):
        assert F.max_drawdown(UPTREND) == pytest.approx(0.0, abs=1e-9)
        dip = pd.concat(
            [pd.Series(np.linspace(100, 150, 150)),
             pd.Series(np.linspace(150, 120, 150))]
        ).reset_index(drop=True)
        assert F.max_drawdown(dip) < -10

    def test_pct_from_extreme(self):
        # 90 vs a high of 100 is -10% (allow float tolerance)
        assert F.pct_from_extreme(90, 100) == pytest.approx(-10.0)
        assert F.pct_from_extreme(90, None) is None
        assert F.pct_from_extreme(90, 0) is None


# ── Fundamental factors ──────────────────────────────────────────────
class TestFundamental:
    INFO = {
        "trailingPE": 25, "forwardPE": 20, "grossMargins": 0.45,
        "returnOnEquity": 0.30, "revenueGrowth": 0.15, "debtToEquity": 50,
        "targetMeanPrice": 120, "currentPrice": 100, "dividendYield": 0.025,
    }

    def test_passthrough_and_scaling(self):
        f = F.compute_fundamental_factors(self.INFO)
        assert f["trailing_pe"] == 25
        assert f["gross_margin"] == pytest.approx(45.0)   # fraction -> percent
        assert f["return_on_equity"] == pytest.approx(30.0)
        assert f["dividend_yield"] == pytest.approx(2.5)

    def test_target_upside(self):
        f = F.compute_fundamental_factors(self.INFO)
        assert f["target_upside"] == pytest.approx(20.0)

    def test_missing_fields_become_none(self):
        f = F.compute_fundamental_factors({})
        assert f["trailing_pe"] is None
        assert f["target_upside"] is None

    def test_nan_and_garbage_become_none(self):
        f = F.compute_fundamental_factors(
            {"trailingPE": float("nan"), "forwardPE": "n/a"}
        )
        assert f["trailing_pe"] is None
        assert f["forward_pe"] is None


# ── Ranking & composites ─────────────────────────────────────────────
class TestRanking:
    VALS = {"A": 10, "B": 20, "C": 30, "D": None}

    def test_none_omitted(self):
        assert "D" not in F.percentile_ranks(self.VALS, +1)

    def test_higher_is_better(self):
        r = F.percentile_ranks(self.VALS, +1)
        assert r["C"] > r["A"]

    def test_lower_is_better(self):
        r = F.percentile_ranks(self.VALS, -1)
        assert r["A"] > r["C"]

    def test_single_value_defaults_to_50(self):
        assert F.percentile_ranks({"A": 5}, +1) == {"A": 50.0}


class TestComposites:
    # A: cheap + profitable + stable; C: expensive + unprofitable + volatile
    PTF = {
        "A": {"trailing_pe": 10, "forward_pe": 9, "gross_margin": 60,
              "return_on_equity": 40, "debt_to_equity": 10, "momentum_12_1": 5,
              "ret_3m": 2, "ret_6m": 3, "price_vs_sma200": 1, "revenue_growth": 20,
              "earnings_growth": 25, "volatility": 15, "beta": 0.8, "max_drawdown": -5},
        "B": {"trailing_pe": 25, "forward_pe": 22, "gross_margin": 40,
              "return_on_equity": 20, "debt_to_equity": 80, "momentum_12_1": 10,
              "ret_3m": 5, "ret_6m": 8, "price_vs_sma200": 5, "revenue_growth": 12,
              "earnings_growth": 10, "volatility": 30, "beta": 1.1, "max_drawdown": -15},
        "C": {"trailing_pe": 80, "forward_pe": 70, "gross_margin": 20,
              "return_on_equity": 5, "debt_to_equity": 200, "momentum_12_1": 40,
              "ret_3m": 20, "ret_6m": 35, "price_vs_sma200": 25, "revenue_growth": 5,
              "earnings_growth": 2, "volatility": 60, "beta": 1.8, "max_drawdown": -40},
    }

    def test_value_favors_cheap(self):
        c = F.compute_composites(self.PTF)
        assert c["A"]["value"] > c["C"]["value"]

    def test_momentum_favors_trending(self):
        c = F.compute_composites(self.PTF)
        assert c["C"]["momentum"] > c["A"]["momentum"]

    def test_quality_favors_profitable(self):
        c = F.compute_composites(self.PTF)
        assert c["A"]["quality"] > c["C"]["quality"]

    def test_low_vol_favors_stable(self):
        c = F.compute_composites(self.PTF)
        assert c["A"]["low_vol"] > c["C"]["low_vol"]
