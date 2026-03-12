"""
Weekly Market Research Pipeline
Fetches market data via yfinance, sends to Claude for analysis, saves summary.
"""

import json
import sys
from datetime import datetime, timedelta

import anthropic
import yfinance as yf

from config import (
    ANTHROPIC_API_KEY,
    ALL_TICKERS,
    WATCHLIST,
    MODEL_WEEKLY,
    MAX_TOKENS_WEEKLY,
    WEEKLY_DIR,
)
from prompts import weekly_research_prompt


def fetch_market_data() -> dict:
    """Pull current market data for all tickers in the watchlist."""
    print(f"Fetching data for {len(ALL_TICKERS)} tickers...")
    data = {}

    for ticker_symbol in ALL_TICKERS:
        try:
            ticker = yf.Ticker(ticker_symbol)

            # Get 1 week of daily history
            hist = ticker.history(period="5d")
            if hist.empty:
                print(f"  ⚠ No data for {ticker_symbol}, skipping")
                continue

            # Get key info
            info = ticker.info or {}

            latest = hist.iloc[-1]
            week_ago = hist.iloc[0] if len(hist) > 1 else latest
            week_change = ((latest["Close"] - week_ago["Close"]) / week_ago["Close"]) * 100

            data[ticker_symbol] = {
                "current_price": round(latest["Close"], 2),
                "week_change_pct": round(week_change, 2),
                "avg_volume": int(hist["Volume"].mean()),
                "latest_volume": int(latest["Volume"]),
                "week_high": round(hist["High"].max(), 2),
                "week_low": round(hist["Low"].min(), 2),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "dividend_yield": info.get("dividendYield"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                "sector": info.get("sector", "ETF/Fund"),
            }
            print(f"  ✓ {ticker_symbol}: ${latest['Close']:.2f} ({week_change:+.2f}%)")

        except Exception as e:
            print(f"  ✗ {ticker_symbol}: Error — {e}")
            continue

    return data


def format_market_data_for_prompt(data: dict) -> str:
    """Format market data into a readable string for the LLM prompt."""
    lines = []

    # Group by category for readability
    for category, tickers in WATCHLIST.items():
        lines.append(f"\n## {category.replace('_', ' ').title()}")
        lines.append("-" * 50)

        for t in tickers:
            if t not in data:
                continue
            d = data[t]
            line = (
                f"{t}: ${d['current_price']} "
                f"({d['week_change_pct']:+.2f}% this week) | "
                f"Vol: {d['avg_volume']:,}"
            )
            if d.get("pe_ratio"):
                line += f" | P/E: {d['pe_ratio']:.1f}"
            if d.get("dividend_yield"):
                line += f" | Div: {d['dividend_yield']:.2%}"
            if d.get("sector") and d["sector"] != "ETF/Fund":
                line += f" | {d['sector']}"
            lines.append(line)

    return "\n".join(lines)


def generate_weekly_summary(market_data_str: str) -> str:
    """Send market data to Claude and get a weekly research summary."""
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    week_date = datetime.now().strftime("%Y-%m-%d")
    prompt = weekly_research_prompt(market_data_str, week_date)

    print(f"\nCalling Claude ({MODEL_WEEKLY}) for weekly summary...")

    message = client.messages.create(
        model=MODEL_WEEKLY,
        max_tokens=MAX_TOKENS_WEEKLY,
        messages=[{"role": "user", "content": prompt}],
    )

    summary = message.content[0].text
    tokens_in = message.usage.input_tokens
    tokens_out = message.usage.output_tokens
    print(f"  Tokens used: {tokens_in} in / {tokens_out} out")

    return summary


def save_weekly_data(raw_data: dict, summary: str) -> str:
    """Save raw data and summary to a dated JSON file."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    filepath = WEEKLY_DIR / f"research_{date_str}.json"

    payload = {
        "date": date_str,
        "raw_data": raw_data,
        "summary": summary,
        "metadata": {
            "tickers_analyzed": len(raw_data),
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

    # Step 1: Fetch market data
    raw_data = fetch_market_data()
    if not raw_data:
        print("ERROR: No market data retrieved. Exiting.")
        sys.exit(1)

    # Step 2: Format for prompt
    formatted = format_market_data_for_prompt(raw_data)

    # Step 3: Generate AI summary
    summary = generate_weekly_summary(formatted)

    # Step 4: Save everything
    filepath = save_weekly_data(raw_data, summary)

    print("\n" + "=" * 60)
    print("WEEKLY SUMMARY PREVIEW")
    print("=" * 60)
    print(summary[:500] + "..." if len(summary) > 500 else summary)
    print("\n✅ Weekly research complete!")

    return filepath


if __name__ == "__main__":
    main()
