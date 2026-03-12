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

| Service | Usage | Monthly Cost |
|---------|-------|-------------|
| **Claude API (Haiku 4.5)** | ~4 weekly summaries + 1 monthly analysis ≈ 50K input / 15K output tokens | **~$0.13** |
| **Claude API (Sonnet 4.6)** | 1 monthly deep analysis ≈ 30K input / 5K output tokens | **~$0.17** |
| **GitHub Actions** | ~5 runs/month × 2-5 min each | **Free** (2,000 min/mo on free tier) |
| **yfinance** | Market data pulls | **Free** |
| **Gmail SMTP** | ~5 emails/month | **Free** |
| **Total** | | **~$0.30/month** |

> **Bottom line:** This app costs roughly 30 cents a month to run. Even if you scale up to daily research or use Sonnet for everything, you'd stay well under $5/month.

### Upgrading to More Powerful Analysis

| Scenario | Estimated Monthly Cost |
|----------|----------------------|
| All Haiku (cheapest) | ~$0.10 |
| Haiku weekly + Sonnet monthly (recommended) | ~$0.30 |
| All Sonnet | ~$1.00 |
| Daily research + Sonnet everything | ~$3-5 |
| Adding web search tool calls | +$0.50-2.00 |

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
