"""
Monthly Recommendation Generator
Reads all weekly research from the past month, pulls fresh data,
and generates a comprehensive investment recommendation report.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import anthropic
import yfinance as yf

from config import (
    ANTHROPIC_API_KEY,
    ALL_TICKERS,
    WATCHLIST,
    MONTHLY_BUDGET,
    RISK_TOLERANCE,
    INVESTMENT_STYLE,
    MODEL_MONTHLY,
    MAX_TOKENS_MONTHLY,
    WEEKLY_DIR,
    MONTHLY_DIR,
)
from prompts import monthly_recommendation_prompt


def load_weekly_summaries() -> str:
    """Load all weekly research summaries from the past ~30 days."""
    cutoff = datetime.now() - timedelta(days=35)  # slight buffer
    summaries = []

    weekly_files = sorted(WEEKLY_DIR.glob("research_*.json"))
    print(f"Found {len(weekly_files)} weekly research files")

    for filepath in weekly_files:
        try:
            with open(filepath) as f:
                data = json.load(f)

            file_date = datetime.strptime(data["date"], "%Y-%m-%d")
            if file_date < cutoff:
                continue

            summaries.append(f"### Week of {data['date']}\n{data['summary']}")
            print(f"  ✓ Loaded {data['date']}")

        except Exception as e:
            print(f"  ✗ Error loading {filepath}: {e}")
            continue

    if not summaries:
        print("  ⚠ No recent weekly summaries found — will proceed with current data only")
        return "No weekly research summaries available for this month."

    return "\n\n---\n\n".join(summaries)


def fetch_current_snapshot() -> str:
    """Get a fresh market snapshot for the recommendation prompt."""
    lines = []
    for category, tickers in WATCHLIST.items():
        lines.append(f"\n## {category.replace('_', ' ').title()}")

        for ticker_symbol in tickers:
            try:
                ticker = yf.Ticker(ticker_symbol)
                hist = ticker.history(period="1mo")
                if hist.empty:
                    continue

                latest = hist.iloc[-1]
                month_ago = hist.iloc[0]
                month_change = ((latest["Close"] - month_ago["Close"]) / month_ago["Close"]) * 100

                info = ticker.info or {}
                line = (
                    f"{ticker_symbol}: ${latest['Close']:.2f} "
                    f"({month_change:+.2f}% this month) | "
                    f"52w range: ${info.get('fiftyTwoWeekLow', 'N/A')}-${info.get('fiftyTwoWeekHigh', 'N/A')}"
                )
                if info.get("trailingPE"):
                    line += f" | P/E: {info['trailingPE']:.1f}"
                lines.append(line)
            except Exception:
                continue

    return "\n".join(lines)


def generate_recommendations(weekly_summaries: str, current_data: str) -> str:
    """Call Claude (Sonnet) to generate monthly investment recommendations."""
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = monthly_recommendation_prompt(
        weekly_summaries=weekly_summaries,
        current_data=current_data,
        budget=MONTHLY_BUDGET,
        risk_tolerance=RISK_TOLERANCE,
        investment_style=INVESTMENT_STYLE,
    )

    print(f"\nCalling Claude ({MODEL_MONTHLY}) for monthly recommendations...")

    message = client.messages.create(
        model=MODEL_MONTHLY,
        max_tokens=MAX_TOKENS_MONTHLY,
        messages=[{"role": "user", "content": prompt}],
    )

    report = message.content[0].text
    tokens_in = message.usage.input_tokens
    tokens_out = message.usage.output_tokens
    print(f"  Tokens used: {tokens_in} in / {tokens_out} out")

    return report


def save_monthly_report(report: str, weekly_summaries: str) -> str:
    """Save the monthly report as both markdown and JSON."""
    month_str = datetime.now().strftime("%Y-%m")

    # Save readable markdown
    md_path = MONTHLY_DIR / f"recommendations_{month_str}.md"
    with open(md_path, "w") as f:
        f.write(f"# AI Investment Advisor — {month_str}\n\n")
        f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")
        f.write(report)
    print(f"  Saved markdown: {md_path}")

    # Save structured JSON for programmatic access
    json_path = MONTHLY_DIR / f"recommendations_{month_str}.json"
    payload = {
        "month": month_str,
        "report": report,
        "config": {
            "budget": MONTHLY_BUDGET,
            "risk_tolerance": RISK_TOLERANCE,
            "investment_style": INVESTMENT_STYLE,
            "model": MODEL_MONTHLY,
        },
        "generated_at": datetime.now().isoformat(),
    }
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"  Saved JSON: {json_path}")

    return str(md_path)


def main():
    """Run the full monthly recommendation pipeline."""
    print("=" * 60)
    print("AI Investment Advisor — Monthly Recommendations")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Budget: ${MONTHLY_BUDGET}/mo | Risk: {RISK_TOLERANCE} | Style: {INVESTMENT_STYLE}")
    print("=" * 60)

    # Step 1: Load weekly research
    print("\n📂 Loading weekly research summaries...")
    weekly_summaries = load_weekly_summaries()

    # Step 2: Get fresh market data
    print("\n📊 Fetching current market snapshot...")
    current_data = fetch_current_snapshot()

    # Step 3: Generate recommendations
    report = generate_recommendations(weekly_summaries, current_data)

    # Step 4: Save
    print("\n💾 Saving monthly report...")
    filepath = save_monthly_report(report, weekly_summaries)

    print("\n" + "=" * 60)
    print("RECOMMENDATION PREVIEW")
    print("=" * 60)
    print(report[:800] + "..." if len(report) > 800 else report)
    print(f"\n✅ Monthly recommendations saved to {filepath}")

    return filepath


if __name__ == "__main__":
    main()
