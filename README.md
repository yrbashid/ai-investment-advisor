# AI Investment Advisor 🤖📈

An automated market research and investment recommendation pipeline that uses Claude (Anthropic's LLM) to analyze financial data and generate monthly investment recommendations for a $1,000/month Robinhood portfolio.

## What It Does

1. **Factor Scoring** — Pulls 2 years of data via `yfinance` and computes technical + fundamental factors for every ticker (momentum, RSI, volatility, beta, valuation, margins, growth, analyst targets), then ranks them cross-sectionally into composite **Value / Momentum / Quality / Growth / Low-Vol** percentile scores. Python does the math; Claude reasons over a clean scorecard.
2. **Macro Regime** — Tracks Treasury yields, the 10Y-3M yield curve, VIX, and the dollar index to frame the rate/volatility backdrop (risk-on vs. risk-off).
3. **Weekly Research** — Claude writes a factor-aware briefing from the scorecard + macro context, using **live web search** to fold in the week's real news (Fed, data prints, earnings).
4. **Monthly Recommendations** — Claude applies an explicit selection rubric (position-sizing caps, sector limits, valuation guardrails, **correlation-aware diversification**) and returns a **structured recommendation via tool-call** — no brittle text parsing. Each pick cites the factor percentiles that justify it.
5. **Email Delivery** — Sends a formatted HTML report via Gmail (supports multiple BCC'd subscribers).
6. **Fully Automated** — Runs on GitHub Actions (free tier) with no server to maintain.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions (Cron)                     │
│                                                             │
│  Weekly (Sun 8am ET):        Monthly (1st of month):        │
│  ┌─────────────────┐        ┌──────────────────────┐       │
│  │ market_research │        │ generate_recs        │       │
│  │   .py           │        │   .py                │       │
│  └────────┬────────┘        └──────────┬───────────┘       │
│           │                            │                    │
│           ▼                            ▼                    │
│  ┌─────────────────┐        ┌──────────────────────┐       │
│  │ yfinance        │        │ Claude API           │       │
│  │ (market data)   │        │ (analysis + recs)    │       │
│  └────────┬────────┘        └──────────┬───────────┘       │
│           │                            │                    │
│           ▼                            ▼                    │
│  ┌─────────────────┐        ┌──────────────────────┐       │
│  │ Claude API      │        │ Gmail (SMTP)         │       │
│  │ (summarize)     │        │ (send report)        │       │
│  └────────┬────────┘        └──────────────────────┘       │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────┐                                       │
│  │ data/weekly/    │  ← JSON research snapshots            │
│  │ data/monthly/   │  ← monthly recommendation reports     │
│  └─────────────────┘                                       │
└─────────────────────────────────────────────────────────────┘
```

## Cost Estimate 💰

Currently configured to use **Claude Opus 4.8** for both weekly and monthly runs — the smartest option, which matters for financial reasoning.

| Service | Usage | Monthly Cost |
|---------|-------|-------------|
| **Claude API (Opus 4.8) — weekly** | 4 runs × ~5K in / 1.5K out tokens | **~$0.75** |
| **Claude API (Opus 4.8) — monthly** | 1 run × ~10K in / 3K out tokens | **~$0.40** |
| **Web search** | ~4 weekly runs × up to 5 searches | **~$0.10** |
| **GitHub Actions** | 5 runs/month × 2-5 min each | **Free** (2,000 min/mo) |
| **yfinance** | Market + macro data pulls | **Free** |
| **Gmail SMTP** | 1 email/month | **Free** |
| **Total** | | **~$1.25/month** |

> **Bottom line:** Roughly $1.25/month with Opus 4.8 + web search. To cut cost, set `ENABLE_WEB_SEARCH = False` or switch `MODEL_WEEKLY` in `src/config.py` to `claude-haiku-4-5-20251001` (~$0.25/mo total) — the monthly Opus run is where reasoning quality matters most.

### Cost by Configuration

| Scenario | Estimated Monthly Cost |
|----------|----------------------|
| All Haiku 4.5 | ~$0.10 |
| Haiku weekly + Opus monthly | ~$0.50 |
| All Opus 4.8 (current default) | ~$1.15 |
| Daily research + Opus everywhere | ~$5-8 |

## Quick Start

### Prerequisites
- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)
- A Gmail account with an [App Password](https://support.google.com/accounts/answer/185833)

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/ai-investment-advisor.git
cd ai-investment-advisor
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
# Edit .env with your actual keys
```

### 3. Run Locally

```bash
# Run weekly research
python src/market_research.py

# Generate monthly recommendations
python src/generate_recs.py

# Send email report
python src/send_report.py
```

### 4. Deploy to GitHub Actions

1. Push to GitHub
2. Go to **Settings → Secrets and variables → Actions**
3. Add these secrets:
   - `ANTHROPIC_API_KEY`
   - `GMAIL_ADDRESS`
   - `GMAIL_APP_PASSWORD`
   - `RECIPIENT_EMAIL`
4. The workflows will run automatically on schedule

## Project Structure

```
ai-investment-advisor/
├── .github/workflows/
│   ├── weekly_research.yml      # Cron: every Sunday 8am ET
│   └── monthly_recommendations.yml  # Cron: 1st of each month
├── src/
│   ├── factors.py               # Factor engine: technicals, fundamentals, ranking, composites
│   ├── macro.py                 # Macro regime (yields, VIX, dollar) + cross-asset correlations
│   ├── market_research.py       # Weekly: scorecard + macro + web-search briefing
│   ├── generate_recs.py         # Monthly: rubric-driven structured recommendations
│   ├── send_report.py           # Emails the report (HTML, multi-recipient)
│   ├── config.py                # Central configuration
│   └── prompts.py               # Prompts, tool schema, markdown renderer
├── docs/
│   └── index.html               # GitHub Pages dashboard (reads data/ JSON)
├── data/                        # Auto-generated research data
│   ├── weekly/
│   └── monthly/
├── tests/
│   ├── test_pipeline.py         # Config, prompts, structured output
│   ├── test_factors.py          # Factor math (offline, synthetic data)
│   └── test_macro.py            # Macro/correlation + web-search fallback
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Customization

### Change Your Budget
Edit `src/config.py`:
```python
MONTHLY_BUDGET = 1000  # Change to your amount
```

### Change Research Focus
Edit `src/prompts.py` to adjust what the AI focuses on — sectors, risk tolerance, investment style, etc.

### Change Schedule
Edit the cron expressions in `.github/workflows/*.yml`.

## Important Disclaimers

⚠️ **This is NOT financial advice.** This tool generates AI-powered research summaries and suggestions for educational purposes. Always do your own due diligence before making investment decisions.

⚠️ **AI can hallucinate.** LLM outputs should be treated as a starting point for research, not as definitive recommendations.

⚠️ **Past performance ≠ future results.** Market data analysis cannot predict future returns.

## License

MIT
