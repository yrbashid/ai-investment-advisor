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
    email_body_text,
    render_report_markdown,
    RECOMMENDATION_TOOL,
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
            scorecard="SPY: $500",
            budget=1000,
            risk_tolerance="moderate",
            investment_style="growth",
        )
        assert "$1000" in prompt
        assert "moderate" in prompt
        assert "growth" in prompt
        assert "Robinhood" in prompt
        assert "submit_recommendations" in prompt  # must instruct the tool call

    def test_email_subject_format(self):
        subject = email_subject("March 2026")
        assert "March 2026" in subject

    def test_email_body_has_disclaimer(self):
        body = email_body_text("Test report content", "March 2026")
        assert "NOT financial advice" in body
        assert "Test report content" in body


class TestStructuredOutput:
    """Test the tool schema and the markdown renderer."""

    RECS = {
        "market_recap": "Tech led the month; rates stable.",
        "allocations": [
            {"ticker": "VOO", "amount": 400, "category": "Core", "conviction": "High",
             "factor_basis": "Low_Vol 100th, broad exposure", "thesis": "Core index anchor."},
            {"ticker": "MSFT", "amount": 350, "category": "Growth", "conviction": "High",
             "factor_basis": "Quality 95th, Value 78th", "thesis": "Cheap, high-quality compounder."},
            {"ticker": "BTC-USD", "amount": 250, "category": "Crypto", "conviction": "Medium",
             "factor_basis": "Momentum 60th", "thesis": "Asymmetric upside, sized small."},
        ],
        "watchlist": [{"ticker": "AMZN", "trigger": "Pullback to $240."}],
        "risks": ["Tech concentration.", "Rate shock."],
        "confidence": "Medium",
        "confidence_rationale": "Strong names, but indices near highs.",
    }

    def test_tool_schema_shape(self):
        schema = RECOMMENDATION_TOOL["input_schema"]
        assert RECOMMENDATION_TOOL["name"] == "submit_recommendations"
        for field in ["market_recap", "allocations", "watchlist", "risks", "confidence"]:
            assert field in schema["properties"]
        item = schema["properties"]["allocations"]["items"]
        assert set(item["required"]) >= {"ticker", "amount", "category", "conviction"}
        assert "Crypto" in item["properties"]["category"]["enum"]

    def test_render_markdown_has_table_and_disclaimer(self):
        md = render_report_markdown(self.RECS, budget=1000)
        assert "| **$400** | **VOO** |" in md
        assert "| **$350** | **MSFT** |" in md
        assert "Total: $1000 across 3 positions" in md
        assert "NOT financial advice" in md
        assert "Medium" in md

    def test_render_markdown_table_parses_back(self):
        """The rendered markdown must survive the dashboard's fallback parser."""
        md = render_report_markdown(self.RECS, budget=1000)
        # Amount in cell[0], ticker in cell[1] — the dashboard's Strategy 1 shape.
        import re
        rows = []
        for line in md.split("\n"):
            if not line.strip().startswith("|"):
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) >= 2 and re.match(r"^\*{0,2}\$\d+\*{0,2}$", cells[0]):
                rows.append(cells[1].replace("*", ""))
        assert rows == ["VOO", "MSFT", "BTC-USD"]


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
