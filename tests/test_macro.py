"""
Tests for the macro/correlation layer (src/macro.py) and the web-search
fallback in the weekly pipeline. All offline — no network, no real API calls.

Run with: python -m pytest tests/test_macro.py -v
"""

import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import macro as M


# ── Macro summary formatting ─────────────────────────────────────────
class TestMacroSummary:
    MACRO = {
        "ten_year": {"value": 4.25, "change": 0.15},
        "three_month": {"value": 4.80, "change": -0.05},
        "vix": {"value": 27.5, "change": 6.0},
        "dollar": {"value": 103.2, "change": -0.4},
        "yield_curve_10y_3m": -0.55,
    }

    def test_contains_all_indicators(self):
        s = M.format_macro_summary(self.MACRO)
        assert "10Y Treasury yield: 4.25%" in s
        assert "3M T-bill yield: 4.8%" in s
        assert "VIX" in s and "27.5" in s
        assert "DXY" in s and "103.2" in s

    def test_inverted_curve_flagged(self):
        s = M.format_macro_summary(self.MACRO)
        assert "INVERTED" in s  # 10Y < 3M

    def test_normal_curve_not_flagged(self):
        m = dict(self.MACRO, yield_curve_10y_3m=1.20)
        s = M.format_macro_summary(m)
        assert "INVERTED" not in s
        assert "normal" in s

    def test_vix_regime_label(self):
        assert "elevated" in M.format_macro_summary(self.MACRO)  # 27.5 -> elevated
        calm = M.format_macro_summary(dict(self.MACRO, vix={"value": 12.0, "change": -1.0}))
        assert "calm" in calm

    def test_missing_data_is_graceful(self):
        assert M.format_macro_summary({}) == "Macro data unavailable."
        partial = M.format_macro_summary({"vix": {"value": 18.0, "change": 0.0}})
        assert "n/a" in partial  # missing indicators show n/a, no crash


# ── Correlation summary ──────────────────────────────────────────────
class TestCorrelations:
    @staticmethod
    def _closes():
        idx = pd.date_range("2025-01-01", periods=120, freq="D")
        rng = np.random.default_rng(7)
        r = rng.normal(0, 0.01, 120)
        # pct_change of cumprod(1+x) equals x exactly, so these correlations are exact:
        a = 100 * np.cumprod(1 + r)
        return {
            "A": pd.Series(a, index=idx),
            "B": pd.Series(2 * a, index=idx),          # identical returns -> corr +1 with A
            "C": pd.Series(100 * np.cumprod(1 - r), index=idx),  # negated returns -> corr -1
        }

    def test_top_pair_is_perfectly_correlated(self):
        c = M.correlation_summary_from_closes(self._closes())
        top = c["top_pairs"][0]
        assert set(top[:2]) == {"A", "B"}
        assert top[2] == pytest.approx(1.0, abs=1e-6)

    def test_anticorrelated_pair_present_and_negative(self):
        c = M.correlation_summary_from_closes(self._closes())
        ac_pairs = {frozenset((a, b)): v for a, b, v in c["top_pairs"]}
        assert ac_pairs[frozenset(("A", "C"))] == pytest.approx(-1.0, abs=1e-6)

    def test_avg_corr_balances_out(self):
        c = M.correlation_summary_from_closes(self._closes())
        # A correlates +1 with B and -1 with C -> average ~0
        assert c["avg_corr"]["A"] == pytest.approx(0.0, abs=1e-6)

    def test_too_few_series_returns_empty(self):
        assert M.correlation_summary_from_closes({"A": pd.Series([1, 2, 3])}) == {}

    def test_format_correlation_summary(self):
        c = M.correlation_summary_from_closes(self._closes())
        s = M.format_correlation_summary(c)
        assert "Most-correlated pairs" in s
        assert "A ↔ B" in s or "B ↔ A" in s

    def test_format_empty_is_blank(self):
        assert M.format_correlation_summary({}) == ""


# ── Web-search fallback in the weekly pipeline ───────────────────────
class TestWebSearchFallback:
    def test_falls_back_when_tool_unavailable(self, monkeypatch):
        import httpx
        import anthropic
        import market_research as MR

        text_block = mock.Mock()
        text_block.type = "text"
        text_block.text = "Weekly briefing body."
        ok_msg = mock.Mock(content=[text_block],
                           usage=mock.Mock(input_tokens=10, output_tokens=20))

        req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        err = anthropic.APIStatusError(
            "web search tool is not enabled", response=httpx.Response(400, request=req), body=None
        )

        create = mock.Mock(side_effect=[err, ok_msg])
        client = mock.Mock()
        client.messages.create = create

        monkeypatch.setattr(MR.anthropic, "Anthropic", lambda **kw: client)
        monkeypatch.setattr(MR, "ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(MR, "ENABLE_WEB_SEARCH", True)

        out = MR.generate_weekly_summary("scorecard", "macro")

        assert out == "Weekly briefing body."
        assert create.call_count == 2
        # First attempt included the web_search tool; the fallback retry did not.
        assert "tools" in create.call_args_list[0].kwargs
        assert "tools" not in create.call_args_list[1].kwargs

    def test_extract_text_joins_text_blocks_only(self):
        import market_research as MR
        search_block = mock.Mock(); search_block.type = "web_search_tool_result"
        t1 = mock.Mock(); t1.type = "text"; t1.text = "Part one. "
        t2 = mock.Mock(); t2.type = "text"; t2.text = "Part two."
        msg = mock.Mock(content=[search_block, t1, t2])
        assert MR._extract_text(msg) == "Part one. Part two."

    def test_extract_text_drops_pre_search_narration(self):
        """Narration emitted before/between searches must not leak into the summary."""
        import market_research as MR
        narration = mock.Mock(); narration.type = "text"; narration.text = "Let me check the news..."
        search = mock.Mock(); search.type = "web_search_tool_result"
        briefing = mock.Mock(); briefing.type = "text"; briefing.text = "# Weekly Briefing\nReal content."
        msg = mock.Mock(content=[narration, search, briefing])
        out = MR._extract_text(msg)
        assert out == "# Weekly Briefing\nReal content."
        assert "Let me check" not in out

    def test_extract_text_no_search_keeps_all(self):
        """With web search off, the whole (single) text block is the briefing."""
        import market_research as MR
        only = mock.Mock(); only.type = "text"; only.text = "# Briefing\nNo search today."
        assert MR._extract_text(mock.Mock(content=[only])) == "# Briefing\nNo search today."
