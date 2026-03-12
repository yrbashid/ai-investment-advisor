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


def email_body_wrapper(report: str) -> str:
    """Wrap the markdown report in an email-friendly format."""
    return f"""Hi,

Your monthly AI-generated investment research report is ready.

{'=' * 60}

{report}

{'=' * 60}

⚠️ REMINDER: This is AI-generated research for educational purposes only.
It is NOT financial advice. Always do your own due diligence.

— Your AI Investment Advisor
(Powered by Claude + yfinance + GitHub Actions)
"""
