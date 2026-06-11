"""
All LLM prompts for the AI Investment Advisor.
Edit these to change the AI's analysis style, focus areas, and output format.
"""


def weekly_research_prompt(
    scorecard: str, macro_summary: str, week_date: str, include_news: bool = True
) -> str:
    """Prompt for the weekly market briefing: macro regime + factor scorecard (+ news)."""
    news_instruction = (
        "Before writing, use web search to check for major market-moving developments in "
        "the past week — Fed / central-bank actions, key economic data (CPI, jobs), notable "
        "earnings, and geopolitical events. Incorporate what you find and attribute it.\n\n"
        if include_news
        else ""
    )
    news_section = (
        "2. **This Week's News** — The most important developments from your web search and "
        "how markets reacted.\n"
        if include_news
        else ""
    )
    return f"""You are a quantitative research analyst preparing a weekly market briefing.

Today's date: {week_date}

You have a MACRO REGIME snapshot and a FACTOR SCORECARD. The scorecard scores every
Robinhood-available asset across five composites — Value, Momentum, Quality, Growth,
Low-Vol — as PERCENTILE RANKS within the universe (0-100, higher = stronger).

<macro_regime>
{macro_summary}
</macro_regime>

<factor_scorecard>
{scorecard}
</factor_scorecard>

{news_instruction}Write a concise weekly briefing (under 500 words) covering:

1. **Market Regime** — Combine the macro snapshot (yields, curve, VIX, dollar) with the
   broad-market factor readings: risk-on or risk-off, and what is the rate / volatility
   backdrop?
{news_section}3. **Factor Leadership** — Which factor is being rewarded right now (e.g. Momentum vs.
   Value)? Which sectors or categories rank highest on it?
4. **Notable Movers** — Names with extreme readings: very strong/weak momentum, deeply
   oversold (RSI < 30) or overbought (RSI > 70) signals, or unusual factor combinations.
5. **Themes to Watch** — What to monitor going into next week.

Cite the percentile and macro data. Do NOT make specific buy/sell recommendations —
that is the monthly report's job.
"""


def monthly_recommendation_prompt(
    weekly_summaries: str,
    scorecard: str,
    macro_summary: str,
    correlation_summary: str,
    budget: int,
    risk_tolerance: str,
    investment_style: str,
) -> str:
    """Prompt for the monthly recommendation. The model MUST answer via tool-call."""
    correlation_block = (
        f"\nCross-asset correlations (use these to keep the portfolio genuinely "
        f"diversified — do not stack highly-correlated names):\n\n<correlations>\n"
        f"{correlation_summary}\n</correlations>\n"
        if correlation_summary
        else ""
    )
    return f"""You are a quantitative portfolio analyst building this month's recommendation
for a long-term investor. You MUST call the `submit_recommendations` tool with your final
answer. Do not write prose outside the tool call.

INVESTOR PROFILE
- Monthly budget: ${budget} (new capital to deploy this month)
- Risk tolerance: {risk_tolerance}
- Investment style: {investment_style}
- Brokerage: Robinhood (only assets available there)
- Horizon: LONG-TERM buy-and-hold with dollar-cost averaging — NOT trading

INPUTS

Macro regime (the rate / volatility / dollar backdrop):

<macro_regime>
{macro_summary}
</macro_regime>

Factor scorecard (Python-computed percentile ranks across the universe — Value,
Momentum, Quality, Growth, Low-Vol; higher = stronger on that factor):

<factor_scorecard>
{scorecard}
</factor_scorecard>
{correlation_block}
Weekly research notes accumulated this month:

<weekly_research>
{weekly_summaries}
</weekly_research>

SELECTION RUBRIC (follow strictly)
1. Recommend 3-6 positions. Amounts are whole dollars and MUST sum to exactly ${budget}.
2. No single position above 40% of the budget; none below 5%.
3. Include at least one Core broad-market holding (e.g. VOO / VTI / SPY) at >= 25% of the
   budget, unless the regime strongly argues otherwise — if you deviate, explain why.
4. Total crypto exposure <= 20% of the budget for a moderate profile (scale with risk
   tolerance: less for conservative, more for aggressive).
5. For a {investment_style} style, weight selection toward the factors that serve it
   (growth -> Momentum / Growth / Quality; value -> Value / Quality; income -> dividend
   plus Quality / Low-Vol). Use the OTHER factors as guardrails:
   - Avoid initiating a position that sits in the bottom decile for Value (i.e. very
     expensive) unless justified by exceptional Growth and Quality ranks.
   - Be cautious adding names with RSI > 80 (overbought); call it out if you do.
6. Diversification: do not fill the portfolio with names that are highly correlated to one
   another (see the correlation block). Favor picks that add a distinct return stream.
7. Let the macro regime shape risk posture: e.g. an inverted curve or elevated VIX argues
   for more Core / Low-Vol weight; a calm risk-on backdrop allows more Growth / Alpha.
8. Each pick's `factor_basis` MUST cite the specific percentile ranks that justify it
   (e.g. "Quality 88th, Value 71st, Momentum 64th").
9. Assign each pick exactly one category: Core, Growth, Tactical, Alpha, Hedge, or Crypto.
10. Set conviction (High / Medium / Low) honestly, based on how strongly the factor ranks,
    macro backdrop, and weekly notes agree.

Also provide: a 3-4 sentence market recap, a 2-3 name watchlist with concrete buy
triggers, 3-5 key portfolio risks, and an overall confidence level with rationale.

This is AI-generated research, NOT financial advice. Be disciplined and data-driven; do
not chase the month's biggest winners on momentum alone.
"""


# ── Structured output schema (Claude tool-use) ───────────────────────
# Forcing the model to answer through this tool eliminates brittle markdown
# parsing: the recommendation comes back as validated structured data.
RECOMMENDATION_TOOL = {
    "name": "submit_recommendations",
    "description": "Submit the finalized monthly investment recommendation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "market_recap": {
                "type": "string",
                "description": "3-4 sentence recap of the month's key themes.",
            },
            "allocations": {
                "type": "array",
                "description": "3-6 recommended positions; amounts must sum to the budget.",
                "items": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "amount": {"type": "integer", "description": "Whole-dollar amount."},
                        "category": {
                            "type": "string",
                            "enum": ["Core", "Growth", "Tactical", "Alpha", "Hedge", "Crypto"],
                        },
                        "conviction": {"type": "string", "enum": ["High", "Medium", "Low"]},
                        "factor_basis": {
                            "type": "string",
                            "description": "Specific factor percentiles justifying the pick.",
                        },
                        "thesis": {"type": "string", "description": "1-3 sentence rationale."},
                    },
                    "required": ["ticker", "amount", "category", "conviction", "factor_basis", "thesis"],
                },
            },
            "watchlist": {
                "type": "array",
                "description": "2-3 names to monitor but not buy yet.",
                "items": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "trigger": {"type": "string", "description": "What would make it a buy."},
                    },
                    "required": ["ticker", "trigger"],
                },
            },
            "risks": {
                "type": "array",
                "description": "3-5 key risks to the recommended allocation.",
                "items": {"type": "string"},
            },
            "confidence": {"type": "string", "enum": ["Low", "Medium", "High"]},
            "confidence_rationale": {"type": "string"},
        },
        "required": [
            "market_recap", "allocations", "watchlist",
            "risks", "confidence", "confidence_rationale",
        ],
    },
}


def render_report_markdown(recs: dict, budget: int) -> str:
    """Render the structured recommendation object into clean markdown."""
    allocations = recs.get("allocations", [])
    total = sum(int(a.get("amount", 0)) for a in allocations)

    lines = ["## Monthly Market Recap", "", recs.get("market_recap", "").strip(), ""]

    lines.append(f"## Recommended Allocation — ${budget}")
    lines.append("")
    lines.append("| Amount | Ticker | Category | Conviction | Factor Basis | Thesis |")
    lines.append("|--------|--------|----------|------------|--------------|--------|")
    for a in allocations:
        lines.append(
            f"| **${a.get('amount', 0)}** | **{a.get('ticker', '')}** | "
            f"{a.get('category', '')} | {a.get('conviction', '')} | "
            f"{a.get('factor_basis', '')} | {a.get('thesis', '')} |"
        )
    lines.append("")
    lines.append(f"**Total: ${total} across {len(allocations)} positions**")
    lines.append("")

    watchlist = recs.get("watchlist", [])
    if watchlist:
        lines += ["## Watchlist", "", "| Ticker | Buy Trigger |", "|--------|-------------|"]
        for w in watchlist:
            lines.append(f"| **{w.get('ticker', '')}** | {w.get('trigger', '')} |")
        lines.append("")

    risks = recs.get("risks", [])
    if risks:
        lines += ["## Risk Assessment", ""]
        lines += [f"- {r}" for r in risks]
        lines.append("")

    lines += [
        "## Confidence Level",
        "",
        f"**{recs.get('confidence', 'N/A')}** — {recs.get('confidence_rationale', '')}",
        "",
        "---",
        "",
        "*This is AI-generated research, NOT financial advice. Always do your own due "
        "diligence. Past performance does not guarantee future results.*",
    ]
    return "\n".join(lines)


def email_subject(month_year: str) -> str:
    """Email subject line for the monthly report."""
    return f"📊 AI Investment Advisor — {month_year} Recommendations"


_INLINE_STYLES = {
    "<h1>": '<h1 style="font-size:20px;font-weight:700;color:#000;margin:28px 0 12px;border-bottom:1px solid #eee;padding-bottom:8px;">',
    "<h2>": '<h2 style="font-size:17px;font-weight:700;color:#000;margin:24px 0 10px;">',
    "<h3>": '<h3 style="font-size:14px;font-weight:600;color:#000;margin:20px 0 8px;">',
    "<h4>": '<h4 style="font-size:13px;font-weight:600;color:#333;margin:16px 0 6px;">',
    "<p>": '<p style="margin:0 0 12px;">',
    "<table>": '<table style="border-collapse:collapse;width:100%;margin:14px 0;font-size:13px;">',
    "<thead>": '<thead style="background:#f5f5f7;">',
    "<th>": '<th style="text-align:left;padding:10px 12px;border-bottom:2px solid #ddd;font-weight:600;">',
    "<td>": '<td style="padding:10px 12px;border-bottom:1px solid #eee;vertical-align:top;">',
    "<ul>": '<ul style="margin:8px 0 12px;padding-left:22px;">',
    "<ol>": '<ol style="margin:8px 0 12px;padding-left:22px;">',
    "<li>": '<li style="margin-bottom:6px;">',
    "<hr />": '<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />',
    "<strong>": '<strong style="font-weight:600;color:#000;">',
    "<em>": '<em style="font-style:italic;color:#444;">',
    "<code>": '<code style="background:#f5f5f7;padding:2px 5px;border-radius:3px;font-family:Menlo,Consolas,monospace;font-size:12px;">',
    "<blockquote>": '<blockquote style="border-left:3px solid #ddd;margin:14px 0;padding:6px 14px;color:#555;">',
}


def _inline_style(html: str) -> str:
    """Add inline styles to rendered markdown HTML for email clients."""
    for tag, replacement in _INLINE_STYLES.items():
        html = html.replace(tag, replacement)
    return html


def email_body_html(report_md: str, month_year: str) -> str:
    """Render the monthly report as a clean HTML email."""
    import markdown
    body = _inline_style(markdown.markdown(report_md, extensions=["tables", "fenced_code"]))

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#1d1d1f;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f5f5f7;padding:24px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" border="0" style="background:#fff;border-radius:12px;overflow:hidden;max-width:600px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        <tr><td style="padding:28px 28px 20px;border-bottom:1px solid #eee;">
          <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#888;font-weight:500;">AI Investment Advisor</div>
          <div style="margin:8px 0 0;font-size:22px;font-weight:700;color:#000;line-height:1.3;">{month_year} Recommendations</div>
        </td></tr>
        <tr><td style="padding:8px 28px 24px;font-size:14px;line-height:1.65;color:#1d1d1f;">{body}</td></tr>
        <tr><td style="padding:18px 28px;background:#fff5f5;border-top:1px solid #ffe0e0;">
          <div style="font-size:11px;color:#a83232;line-height:1.55;">
            <strong style="font-weight:600;">⚠ Disclaimer:</strong> AI-generated research for educational purposes only.
            NOT financial advice. Past performance does not guarantee future results. Always do your own due diligence.
          </div>
        </td></tr>
        <tr><td style="padding:14px 28px;background:#fafafa;text-align:center;font-size:10px;color:#999;letter-spacing:0.3px;">
          Powered by Claude + yfinance + GitHub Actions
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def email_body_text(report_md: str, month_year: str) -> str:
    """Plain-text fallback for email clients that don't render HTML."""
    return (
        f"AI Investment Advisor — {month_year} Recommendations\n"
        f"{'=' * 60}\n\n"
        f"{report_md}\n\n"
        f"{'=' * 60}\n"
        "⚠ Disclaimer: AI-generated research for educational purposes only.\n"
        "NOT financial advice. Always do your own due diligence.\n"
    )
