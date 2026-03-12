"""
Basic tests for the AI Investment Advisor pipeline.
Run with: python -m pytest tests/ -v
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import ALL_TICKERS, WATCHLIST, MONTHLY_BUDGET, WEEKLY_DIR, MONTHLY_DIR
from prompts import (
    weekly_research_prompt,
    monthly_recommendation_prompt,
    email_subject,
    email_body_wrapper,
)


class TestConfig:
    """Test that configuration is sane."""

    def test_tickers_not_empty(self):
        assert len(ALL_TICKERS) > 0, "Watchlist should have tickers"

    def test_watchlist_categories(self):
        expected = {"broad_market_etfs", "sector_etfs", "crypto", "growth_stocks", "dividend_stocks", "bonds_alternatives"}
        assert set(WATCHLIST.keys()) == expected

    def test_budget_positive(self):
        assert MONTHLY_BUDGET > 0

    def test_no_duplicate_tickers(self):
        assert len(ALL_TICKERS) == len(set(ALL_TICKERS)), "Tickers should be deduplicated"

    def test_data_dirs_exist(self):
        assert WEEKLY_DIR.exists(), f"{WEEKLY_DIR} should exist"
        assert MONTHLY_DIR.exists(), f"{MONTHLY_DIR} should exist"


class TestPrompts:
    """Test that prompt templates render correctly."""

    def test_weekly_prompt_contains_data(self):
        prompt = weekly_research_prompt("SPY: $500 (+1.5%)", "2026-03-12")
        assert "SPY: $500" in prompt
        assert "2026-03-12" in prompt

    def test_monthly_prompt_contains_config(self):
        prompt = monthly_recommendation_prompt(
            weekly_summaries="Week 1 summary",
            current_data="SPY: $500",
            budget=1000,
            risk_tolerance="moderate",
            investment_style="growth",
        )
        assert "$1000" in prompt
        assert "moderate" in prompt
        assert "growth" in prompt
        assert "Robinhood" in prompt

    def test_email_subject_format(self):
        subject = email_subject("March 2026")
        assert "March 2026" in subject

    def test_email_body_has_disclaimer(self):
        body = email_body_wrapper("Test report content")
        assert "NOT financial advice" in body
        assert "Test report content" in body


class TestDataIntegrity:
    """Test data file structure (when files exist)."""

    def test_weekly_json_schema(self):
        """If weekly files exist, verify their schema."""
        for filepath in WEEKLY_DIR.glob("research_*.json"):
            with open(filepath) as f:
                data = json.load(f)
            assert "date" in data
            assert "raw_data" in data
            assert "summary" in data
            assert "metadata" in data
            break  # just test the first one
