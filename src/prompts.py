"""
All LLM prompts for the AI Investment Advisor.
Edit these to change the AI's analysis style, focus areas, and output format.
"""


def weekly_research_prompt(market_data: str, week_date: str) -> str:
    """Prompt for weekly market research summary."""
    return f"""You are a financial research analyst preparing a weekly market briefing.

Today's date: {week_date}

Below is this week's market data for a watchlist of stocks and ETFs available on Robinhood.
The data includes recent price action, volume, and key metrics.

<market_data>
{market_data}
</market_data>

Please provide a concise weekly research summary covering:

1. **Market Overview** — How did the broad market (SPY, QQQ) perform this week? Any notable trends?
2. **Sector Performance** — Which sectors outperformed or underperformed? Why might that be?
3. **Notable Movers** — Any individual stocks with significant price changes or volume spikes?
4. **Key Metrics** — Highlight any concerning or encouraging signals (P/E ratios, momentum, etc.)
5. **Themes to Watch** — What trends or events should we monitor going into next week?

Keep the summary under 500 words. Be factual and data-driven.
Do NOT make specific buy/sell recommendations — save that for the monthly report.
"""


def monthly_recommendation_prompt(
    weekly_summaries: str,
    current_data: str,
    budget: int,
    risk_tolerance: str,
    investment_style: str,
) -> str:
    """Prompt for monthly investment recommendation report."""
    return f"""You are a financial research analyst preparing a monthly investment recommendation report.

The investor has the following profile:
- Monthly investment budget: ${budget}
- Risk tolerance: {risk_tolerance}
- Investment style: {investment_style}
- Brokerage: Robinhood (so only assets available there)
- This is for LONG-TERM investing, not day trading

Here are the weekly research summaries from the past month:

<weekly_research>
{weekly_summaries}
</weekly_research>

Here is the current market snapshot:

<current_data>
{current_data}
</current_data>

Please generate a monthly investment recommendation report with:

1. **Monthly Market Recap** (3-4 sentences)
   - What were the key themes this month?

2. **Recommended Allocation** for ${budget}
   - Provide specific ticker symbols and dollar amounts
   - Aim for 3-6 positions (don't over-diversify a small portfolio)
   - Include the reasoning for each pick
   - Example format: "$300 → VOO (S&P 500 index — core holding for broad exposure)"

3. **Watchlist** (2-3 tickers)
   - Stocks/ETFs to monitor but not buy yet, and what trigger would make them a buy

4. **Risk Assessment**
   - What could go wrong with these recommendations?
   - What would cause you to change the allocation?

5. **Confidence Level**
   - Rate your overall confidence in these recommendations: Low / Medium / High
   - Brief explanation of why

IMPORTANT DISCLAIMERS TO INCLUDE:
- This is AI-generated research, NOT financial advice
- The investor should do their own due diligence
- Past performance does not guarantee future results

Format the report in clean markdown.
"""


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
