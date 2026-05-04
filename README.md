# AI Investment Advisor 🤖📈

An automated market research and investment recommendation pipeline that uses Claude (Anthropic's LLM) to analyze financial data and generate monthly investment recommendations for a $1,000/month Robinhood portfolio.

## What It Does

1. **Weekly Research** — Pulls market data via `yfinance`, fetches recent news via web search, and analyzes sector trends
2. **Monthly Recommendations** — Synthesizes a month of research into actionable buy/hold/sell recommendations for assets available on Robinhood
3. **Email Delivery** — Sends you a formatted report via Gmail so you never miss a recommendation
4. **Fully Automated** — Runs on GitHub Actions (free tier) with no server to maintain

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

Currently configured to use **Claude Opus 4.7** for both weekly and monthly runs — the smartest option, which matters for financial reasoning.

| Service | Usage | Monthly Cost |
|---------|-------|-------------|
| **Claude API (Opus 4.7) — weekly** | 4 runs × ~5K in / 1.5K out tokens | **~$0.75** |
| **Claude API (Opus 4.7) — monthly** | 1 run × ~10K in / 3K out tokens | **~$0.40** |
| **GitHub Actions** | 5 runs/month × 2-5 min each | **Free** (2,000 min/mo) |
| **yfinance** | Market data pulls | **Free** |
| **Gmail SMTP** | 1 email/month | **Free** |
| **Total** | | **~$1.15/month** |

> **Bottom line:** Roughly $1/month with Opus 4.7. To cut cost further, switch `MODEL_WEEKLY` in `src/config.py` to `claude-haiku-4-5-20251001` (~$0.20/mo total) — the monthly Opus run is where reasoning quality matters most.

### Cost by Configuration

| Scenario | Estimated Monthly Cost |
|----------|----------------------|
| All Haiku 4.5 | ~$0.10 |
| Haiku weekly + Opus monthly | ~$0.50 |
| All Opus 4.7 (current default) | ~$1.15 |
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
│   ├── market_research.py       # Fetches & analyzes market data
│   ├── generate_recs.py         # Produces investment recommendations
│   ├── send_report.py           # Emails the report
│   ├── config.py                # Central configuration
│   └── prompts.py               # All LLM prompts (easy to tweak)
├── data/                        # Auto-generated research data (gitignored)
│   ├── weekly/
│   └── monthly/
├── tests/
│   └── test_pipeline.py
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
