"""
Weekly Market Research Pipeline

Computes a factor scorecard (technical + fundamental factors, ranked
cross-sectionally) for the watchlist, sends the scorecard to Claude for a
factor-aware briefing, and saves both the scorecard and the summary.
"""

import json
import sys
import time
from datetime import datetime

import anthropic

from config import (
    ANTHROPIC_API_KEY,
    ALL_TICKERS,
    WATCHLIST,
    MODEL_WEEKLY,
    MAX_TOKENS_WEEKLY,
    WEEKLY_DIR,
)
from factors import compute_factors, format_factor_scorecard
from prompts import weekly_research_prompt


def build_raw_data(factor_data: dict) -> dict:
    """
    Compact per-ticker view (price + short-term changes) kept for the
    dashboard's "top movers" display and backward compatibility.
    """
    raw = {}
    for ticker, d in factor_data.items():
        tech = d.get("technical", {})
        week = tech.get("ret_1w")
        month = tech.get("ret_1m")
        raw[ticker] = {
            "current_price": d.get("price"),
            "week_change_pct": round(week, 2) if week is not None else 0.0,
            "month_change_pct": round(month, 2) if month is not None else 0.0,
            "sector": d.get("sector", "ETF/Fund"),
        }
    return raw


def generate_weekly_summary(scorecard: str) -> str:
    """Send the factor scorecard to Claude and get a weekly briefing."""
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    week_date = datetime.now().strftime("%Y-%m-%d")
    prompt = weekly_research_prompt(scorecard, week_date)

    print(f"\nCalling Claude ({MODEL_WEEKLY}) for weekly summary...")
    for attempt in range(5):
        try:
            message = client.messages.create(
                model=MODEL_WEEKLY,
                max_tokens=MAX_TOKENS_WEEKLY,
                messages=[{"role": "user", "content": prompt}],
            )
            summary = message.content[0].text
            print(f"  Tokens used: {message.usage.input_tokens} in / {message.usage.output_tokens} out")
            return summary
        except anthropic.APIStatusError as e:
            if e.status_code < 500 and e.status_code != 429:
                raise
            wait = 30 * (attempt + 1)
            print(f"  ⚠ API {e.status_code}, retrying in {wait}s (attempt {attempt + 1}/5)...")
            time.sleep(wait)
        except anthropic.APIConnectionError:
            wait = 30 * (attempt + 1)
            print(f"  ⚠ Connection error, retrying in {wait}s (attempt {attempt + 1}/5)...")
            time.sleep(wait)

    print("ERROR: API still failing after 5 retries")
    sys.exit(1)


def save_weekly_data(factor_data: dict, scorecard: str, summary: str) -> str:
    """Save the factor scorecard, raw movers data, and summary to a dated JSON."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    filepath = WEEKLY_DIR / f"research_{date_str}.json"

    payload = {
        "date": date_str,
        "raw_data": build_raw_data(factor_data),
        "factors": factor_data,
        "scorecard": scorecard,
        "summary": summary,
        "metadata": {
            "tickers_analyzed": len(factor_data),
            "model": MODEL_WEEKLY,
            "generated_at": datetime.now().isoformat(),
        },
    }

    with open(filepath, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(f"\nSaved weekly research to {filepath}")
    return str(filepath)


def main():
    """Run the full weekly research pipeline."""
    print("=" * 60)
    print("AI Investment Advisor — Weekly Research")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Step 1: Compute the factor scorecard (Python does the math)
    factor_data = compute_factors(ALL_TICKERS)
    if not factor_data:
        print("ERROR: No market data retrieved. Exiting.")
        sys.exit(1)

    # Step 2: Format the scorecard for the prompt
    scorecard = format_factor_scorecard(factor_data, WATCHLIST)

    # Step 3: Generate the factor-aware AI briefing
    summary = generate_weekly_summary(scorecard)

    # Step 4: Save everything
    filepath = save_weekly_data(factor_data, scorecard, summary)

    print("\n" + "=" * 60)
    print("WEEKLY SUMMARY PREVIEW")
    print("=" * 60)
    print(summary[:500] + "..." if len(summary) > 500 else summary)
    print("\n✅ Weekly research complete!")

    return filepath


if __name__ == "__main__":
    main()
