"""
Monthly Recommendation Generator

Reads the past month's weekly research, computes a fresh factor scorecard, and
asks Claude to produce a criteria-driven recommendation. The model answers via
a forced tool-call, so the result comes back as validated structured data
(no markdown scraping). We store the structured object, a rendered markdown
report, and a backward-compatible JSON payload.
"""

import json
import sys
import time
from datetime import datetime, timedelta

import anthropic

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
from factors import compute_factors, format_factor_scorecard
from macro import (
    compute_macro_context,
    format_macro_summary,
    compute_correlation_summary,
    format_correlation_summary,
)
from prompts import (
    monthly_recommendation_prompt,
    render_report_markdown,
    RECOMMENDATION_TOOL,
)
from tracking import (
    load_ledger,
    save_ledger,
    record_recommendations,
    update_performance,
)


def load_weekly_summaries() -> str:
    """Load all weekly research summaries from the past ~35 days."""
    cutoff = datetime.now() - timedelta(days=35)
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
        print("  ⚠ No recent weekly summaries found — proceeding with current factors only")
        return "No weekly research summaries available for this month."

    return "\n\n---\n\n".join(summaries)


def validate_recommendations(recs: dict, budget: int) -> None:
    """Log (don't fail) if the model's allocation violates the budget rule."""
    allocations = recs.get("allocations", [])
    total = sum(int(a.get("amount", 0)) for a in allocations)
    if total != budget:
        print(f"  ⚠ Allocations sum to ${total}, expected ${budget} (off by ${total - budget})")
    if not (3 <= len(allocations) <= 6):
        print(f"  ⚠ {len(allocations)} positions recommended (rubric asks for 3-6)")


def generate_recommendations(
    weekly_summaries: str, scorecard: str, macro_summary: str, correlation_summary: str
) -> dict:
    """Call Claude with a forced tool-call; return the structured recommendation."""
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = monthly_recommendation_prompt(
        weekly_summaries=weekly_summaries,
        scorecard=scorecard,
        macro_summary=macro_summary,
        correlation_summary=correlation_summary,
        budget=MONTHLY_BUDGET,
        risk_tolerance=RISK_TOLERANCE,
        investment_style=INVESTMENT_STYLE,
    )

    print(f"\nCalling Claude ({MODEL_MONTHLY}) for monthly recommendations...")
    for attempt in range(5):
        try:
            message = client.messages.create(
                model=MODEL_MONTHLY,
                max_tokens=MAX_TOKENS_MONTHLY,
                tools=[RECOMMENDATION_TOOL],
                tool_choice={"type": "tool", "name": "submit_recommendations"},
                messages=[{"role": "user", "content": prompt}],
            )
            print(f"  Tokens used: {message.usage.input_tokens} in / {message.usage.output_tokens} out")
            for block in message.content:
                if block.type == "tool_use" and block.name == "submit_recommendations":
                    return block.input
            print("ERROR: model did not return a submit_recommendations tool call")
            sys.exit(1)
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


def save_monthly_report(recs: dict, report_md: str, macro: dict) -> str:
    """Save markdown (for email) + JSON (structured recs for the dashboard)."""
    month_str = datetime.now().strftime("%Y-%m")

    md_path = MONTHLY_DIR / f"recommendations_{month_str}.md"
    with open(md_path, "w") as f:
        f.write(f"# AI Investment Advisor — {month_str}\n\n")
        f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")
        f.write(report_md)
    print(f"  Saved markdown: {md_path}")

    json_path = MONTHLY_DIR / f"recommendations_{month_str}.json"
    payload = {
        "month": month_str,
        "recommendations": recs,   # structured object — dashboard reads this directly
        "report": report_md,       # rendered markdown — email + backward-compat parser
        "macro": macro,            # macro regime snapshot for the dashboard
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

    # Step 1: Load the month's weekly research
    print("\n📂 Loading weekly research summaries...")
    weekly_summaries = load_weekly_summaries()

    # Step 2: Compute a fresh factor scorecard
    print("\n📊 Computing current factor scorecard...")
    factor_data = compute_factors(ALL_TICKERS)
    if not factor_data:
        print("ERROR: No market data retrieved. Exiting.")
        sys.exit(1)
    scorecard = format_factor_scorecard(factor_data, WATCHLIST)

    # Step 3: Macro regime + cross-asset correlations
    print("\n🌐 Computing macro regime + correlations...")
    macro = compute_macro_context()
    macro_summary = format_macro_summary(macro)
    correlation_summary = format_correlation_summary(compute_correlation_summary(ALL_TICKERS))

    # Step 4: Generate structured recommendations
    recs = generate_recommendations(weekly_summaries, scorecard, macro_summary, correlation_summary)
    validate_recommendations(recs, MONTHLY_BUDGET)

    # Step 5: Render markdown and save
    print("\n💾 Saving monthly report...")
    report_md = render_report_markdown(recs, MONTHLY_BUDGET)
    filepath = save_monthly_report(recs, report_md, macro)

    # Step 6: Record this month's picks (with entry prices) into the tracking ledger
    print("\n📒 Recording recommendations into the tracking ledger...")
    month_str = datetime.now().strftime("%Y-%m")
    date_str = datetime.now().strftime("%Y-%m-%d")
    prices = {t: d["price"] for t, d in factor_data.items()}
    ledger = record_recommendations(recs, prices, month_str, date_str, load_ledger())
    save_ledger(ledger)
    update_performance(prices, ledger)

    print("\n" + "=" * 60)
    print("RECOMMENDATION PREVIEW")
    print("=" * 60)
    print(report_md[:800] + "..." if len(report_md) > 800 else report_md)
    print(f"\n✅ Monthly recommendations saved to {filepath}")

    return filepath


if __name__ == "__main__":
    main()
