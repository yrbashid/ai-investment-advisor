"""
Central configuration for AI Investment Advisor.
All settings in one place — edit here to customize.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── API Keys (loaded from environment / GitHub Secrets) ──────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "")

# ── Investment Parameters ────────────────────────────────────────────
MONTHLY_BUDGET = 1000  # dollars per month to invest
RISK_TOLERANCE = "moderate"  # conservative, moderate, aggressive
INVESTMENT_STYLE = "growth"  # growth, value, balanced, income

# ── Robinhood-Available Asset Universe ──────────────────────────────
# ETFs, crypto, and individual stocks available on Robinhood.
WATCHLIST = {
    "broad_market_etfs": ["SPY", "QQQ", "VTI", "IWM", "DIA", "VOO"],
    "sector_etfs": [
        "XLK",   # Technology
        "XLF",   # Financials
        "XLV",   # Healthcare
        "XLE",   # Energy
        "XLY",   # Consumer Discretionary
        "XLP",   # Consumer Staples
        "XLI",   # Industrials
        "XLU",   # Utilities
        "XLRE",  # Real Estate
        "XLC",   # Communication Services
        "XLB",   # Materials
    ],
    "crypto": [
        "BTC-USD",   # Bitcoin
        "ETH-USD",   # Ethereum
        "SOL-USD",   # Solana
        "DOGE-USD",  # Dogecoin
        "AVAX-USD",  # Avalanche
        "LINK-USD",  # Chainlink
        "XRP-USD",   # Ripple
        "ADA-USD",   # Cardano
    ],
    "growth_stocks": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "AVGO", "CRM", "AMD",
        "NFLX", "PLTR", "SNOW", "SHOP", "COIN",
    ],
    "dividend_stocks": [
        "JNJ", "PG", "KO", "PEP", "VZ",
        "T", "XOM", "CVX", "ABBV", "MRK",
    ],
    "bonds_alternatives": [
        "BND",   # Total Bond Market
        "TLT",   # Long-term Treasury
        "GLD",   # Gold
        "SLV",   # Silver
        "VNQ",   # Real Estate
    ],
}

# Flatten for easy iteration
ALL_TICKERS = []
for category_tickers in WATCHLIST.values():
    ALL_TICKERS.extend(category_tickers)
ALL_TICKERS = list(set(ALL_TICKERS))  # deduplicate

# ── Model Configuration ─────────────────────────────────────────────
# Opus 4.8 for both: best reasoning quality, manageable cost at this volume
MODEL_WEEKLY = "claude-opus-4-8"
MODEL_MONTHLY = "claude-opus-4-8"
MAX_TOKENS_WEEKLY = 2048
MAX_TOKENS_MONTHLY = 8192  # generous headroom so structured tool-call JSON never truncates

# ── Macro Regime Tickers ────────────────────────────────────────────
# Yahoo symbols for the macro context layer (yields are quoted in percent).
MACRO_TICKERS = {
    "ten_year": "^TNX",      # 10-Year Treasury yield
    "three_month": "^IRX",   # 13-week T-bill yield (short rate)
    "vix": "^VIX",           # CBOE volatility index
    "dollar": "DX-Y.NYB",    # US Dollar Index
}

# ── Web Search (Anthropic server-side tool) ─────────────────────────
# Adds real recent-news awareness to the weekly briefing. Falls back
# gracefully to no-search if the account doesn't have the tool enabled.
ENABLE_WEB_SEARCH = True
WEB_SEARCH_TOOL_TYPE = "web_search_20250305"  # bump if Anthropic ships a newer version
WEB_SEARCH_MAX_USES = 5

# ── File Paths ──────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
WEEKLY_DIR = DATA_DIR / "weekly"
MONTHLY_DIR = DATA_DIR / "monthly"

# Create directories if they don't exist
WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
