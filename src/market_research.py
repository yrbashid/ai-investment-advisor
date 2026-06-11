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
    ENABLE_WEB_SEARCH,
    WEB_SEARCH_TOOL_TYPE,
    WEB_SEARCH_MAX_USES,
)
from factors import compute_factors, format_factor_scorecard
from macro import compute_macro_context, format_macro_summary
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


def _extract_text(message) -> str:
    """Join all text blocks (a web-search response interleaves search results)."""
    return "".join(
        b.text for b in message.content if getattr(b, "type", None) == "text"
    ).strip()


def generate_weekly_summary(scorecard: str, macro_summary: str) -> str:
    """Send the scorecard + macro context to Claude (with web search) for a briefing."""
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    week_date = datetime.now().strftime("%Y-%m-%d")
    use_search = ENABLE_WEB_SEARCH

    print(f"\nCalling Claude ({MODEL_WEEKLY}) for weekly summary"
          f"{' (with web search)' if use_search else ''}...")

    for attempt in range(5):
        prompt = weekly_research_prompt(scorecard, macro_summary, week_date, include_news=use_search)
        kwargs = {
            "model": MODEL_WEEKLY,
            "max_tokens": MAX_TOKENS_WEEKLY,
            "messages": [{"role": "user", "content": prompt}],
        }
        if use_search:
            kwargs["tools"] = [{
                "type": WEB_SEARCH_TOOL_TYPE,
                "name": "web_search",
                "max_uses": WEB_SEARCH_MAX_USES,
            }]
        try:
            message = client.messages.create(**kwargs)
            summary = _extract_text(message)
            print(f"  Tokens used: {message.usage.input_tokens} in / {message.usage.output_tokens} out")
            return summary
        except anthropic.APIStatusError as e:
            # If the account doesn't have the web-search tool, disable it and retry.
            if use_search and e.status_code == 400 and "search" in str(e).lower():
                print("  ⚠ Web search tool unavailable — retrying without it")
                use_search = False
                continue
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


def save_weekly_data(factor_data: dict, scorecard: str, summary: str, macro: dict) -> str:
    """Save the factor scorecard, raw movers data, macro context, and summary."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    filepath = WEEKLY_DIR / f"research_{date_str}.json"

    payload = {
        "date": date_str,
        "raw_data": build_raw_data(factor_data),
        "factors": factor_data,
        "scorecard": scorecard,
        "macro": macro,
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

    # Step 3: Fetch the macro regime context
    print("\n🌐 Fetching macro regime (yields, VIX, dollar)...")
    macro = compute_macro_context()
    macro_summary = format_macro_summary(macro)

    # Step 4: Generate the factor-aware AI briefing (with web search)
    summary = generate_weekly_summary(scorecard, macro_summary)

    # Step 5: Save everything
    filepath = save_weekly_data(factor_data, scorecard, summary, macro)

    print("\n" + "=" * 60)
    print("WEEKLY SUMMARY PREVIEW")
    print("=" * 60)
    print(summary[:500] + "..." if len(summary) > 500 else summary)
    print("\n✅ Weekly research complete!")

    return filepath


if __name__ == "__main__":
    main()
