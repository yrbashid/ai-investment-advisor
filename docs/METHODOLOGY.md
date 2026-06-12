# How the AI Investment Advisor Works

*A plain-English guide to what the system considers, how it decides, and what
makes it more than "ask a chatbot for stock tips."*

> ⚠️ **This is AI-generated research for educational purposes — not financial
> advice.** It can be wrong. Past performance does not guarantee future results.
> Always do your own due diligence. See [Honest Limitations](#honest-limitations).

---

## 1. The core idea

Most "AI stock picker" projects do something naive: they paste a table of prices
into a chatbot and ask "what should I buy?" Large language models are *bad* at
arithmetic over dozens of numbers and *good* at reasoning over well-organized
summaries. So this system splits the work:

> **Python computes the hard numbers. Claude reasons over a clean scorecard
> under explicit rules.**

Every month it deploys a fixed budget ($1,000) across a long-term, buy-and-hold
portfolio of assets available on Robinhood. Every week it refreshes its market
read. And it keeps score against the S&P 500 so you can see whether the approach
actually adds value.

---

## 2. What changed (the redesign at a glance)

| Area | Before | After |
|------|--------|-------|
| **Inputs** | Raw price table eyeballed by the model | 30+ technical & fundamental factors computed in Python, ranked across the universe |
| **Decision basis** | "Vibes" from recent price moves | Five factor scores + macro regime + correlations + live news, under an explicit rubric |
| **Output** | Free-text markdown, scraped with fragile regex | Structured data via a forced tool-call — validated, auditable |
| **Context** | Prices only | Treasury yields, yield curve, VIX, the dollar, and cross-asset correlations |
| **News** | None (despite claims) | Live web search each week |
| **Accountability** | None | Every pick tracked vs SPY; a track record with alpha |
| **Model** | — | Claude Opus 4.8 |

The redesign was delivered in four pillars: **(1)** a factor engine, **(2)** a
macro + correlation + news layer, **(3)** criteria-driven structured output, and
**(4)** outcome tracking.

---

## 3. How a recommendation is made (the pipeline)

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  1. COLLECT   yfinance: 2 years of history for ~55 tickers       │
  │  2. COMPUTE   Python derives 30+ factors per ticker             │
  │  3. RANK      Convert to percentiles + 5 composite scores        │
  │  4. FRAME     Macro regime (yields, curve, VIX, dollar)          │
  │  5. RELATE    Correlation matrix (who moves together)            │
  │  6. READ      Live web search for the week's real news           │
  │  7. DECIDE    Claude applies an explicit rubric → structured rec │
  │  8. RECORD    Log each pick + entry price; score vs SPY over time │
  └─────────────────────────────────────────────────────────────────┘
```

Steps 1–6 are deterministic Python. Step 7 is where Claude exercises judgment —
but inside hard constraints. Step 8 closes the loop so the system is measurable.

---

## 4. What the model considers

### 4a. The five factor scores

For every asset, Python computes dozens of raw metrics and distills them into
five **composite scores**, each expressed as a **percentile rank (0–100) within
the universe** — so "Quality 92" means "more profitable/sturdier than 92% of the
watchlist," not an abstract number.

| Factor | Plain meaning | Built from |
|--------|---------------|-----------|
| **Value** | How cheap is it? | Trailing & forward P/E, PEG, Price/Sales, Price/Book, EV/EBITDA |
| **Momentum** | Is it trending up? | 12-month-minus-1-month return, 3- & 6-month returns, price vs. 200-day average |
| **Quality** | Is the business strong? | Gross/operating margins, return on equity & assets, low debt |
| **Growth** | Is it growing? | Revenue growth, earnings growth |
| **Low-Vol** | How calm/stable is it? | Annualized volatility, beta vs. SPY, max drawdown |

Why percentiles instead of raw values? Because "P/E of 28" is meaningless in
isolation, but "cheaper than 70% of its peers right now" is a decision. Ranking
**cross-sectionally** (against the rest of the universe, today) is how real
quantitative funds frame factor exposure.

Supporting raw signals also reach the model: **RSI** (overbought/oversold),
**volatility**, **forward P/E**, and **distance from the 52-week high**.

### 4b. The macro regime

Factors describe individual assets; macro describes the *weather* they trade in:

- **10-Year & 3-Month Treasury yields** — the cost of money.
- **Yield curve (10Y − 3M)** — when it inverts (short rates above long), it's a
  classic recession warning, and the system flags it.
- **VIX** — the market's "fear gauge"; labeled calm / normal / elevated / high-fear.
- **US Dollar Index** — a rising dollar often signals risk-aversion.

This shifts the *risk posture*: an inverted curve or a spiking VIX pushes the
model toward more Core/Low-Vol weight; a calm, risk-on backdrop allows more
Growth/Alpha.

### 4c. Cross-asset correlations

Holding five tickers isn't diversification if they all move together. The system
computes a **correlation matrix** over a year of daily returns and tells the
model which names are effectively the same bet (e.g. SPY, VOO, and QQQ are nearly
identical) and which add a genuinely different return stream (e.g. gold, bonds).
The rubric then forbids stacking highly-correlated picks.

### 4d. Live news

Each week, Claude uses **web search** to pull the real events moving markets —
Fed decisions, inflation/jobs data, earnings, geopolitics — and folds them into
the briefing. (In one run it correctly surfaced an oil-supply shock and tilted
toward energy in response.) If the search tool is unavailable, it degrades
gracefully to factors + macro.

### 4e. The selection rubric (the rules it must obey)

This is the discipline layer. The monthly decision must satisfy:

1. **3–6 positions**, dollar amounts summing **exactly** to the budget.
2. **No position above 40%** of the budget; none below 5%.
3. **At least 25% in a Core broad-market holding** (e.g. VOO) unless the regime
   argues otherwise — and it must explain any deviation.
4. **Crypto capped at ~20%** for a moderate risk profile (scaled by risk tolerance).
5. **Style-weighted**: a growth mandate leans on Momentum/Growth/Quality, with
   **Value as a guardrail** — it won't buy something in the most-expensive decile
   unless exceptional growth and quality justify it.
6. **Overbought caution**: flags anything with RSI > 80.
7. **Diversification**: avoid correlated clusters.
8. **Every pick must cite the specific factor percentiles that justify it**
   (e.g. "Quality 88th, Value 71st, Momentum 64th").
9. Each pick gets a **category** (Core/Growth/Tactical/Alpha/Hedge/Crypto) and an
   honest **conviction** (High/Medium/Low).

---

## 5. How it actually "decides"

It's a division of labor between objective computation and constrained judgment:

- **Python supplies objective signal.** Rankings, correlations, and macro values
  aren't opinions — they're computed the same way every time. This removes the
  LLM's weakest skill (arithmetic over many numbers) from the loop.
- **Claude supplies judgment, on a leash.** Given the scorecard, the macro
  backdrop, the correlations, and the week's news, it weighs trade-offs a formula
  can't — e.g. "this name is cheap *and* high-quality, but it's overbought and
  highly correlated with two other picks, so size it smaller." The rubric bounds
  that judgment so it can't, say, dump everything into one momentum darling.
- **The structured output enforces the discipline.** Instead of writing prose we
  hope to parse, the model returns its answer through a **validated schema** (a
  "tool call"). If the data doesn't fit — wrong types, missing fields — it's
  rejected and retried. The recommendation is auditable by construction.

The result is reproducible *reasoning*, not a black-box guess: you can read,
for every dollar, exactly which factors and conditions drove the call.

---

## 6. Sophistications

What lifts this above a toy:

- **Factor-model foundation.** The five composites mirror the factors with real
  academic and industry support (value, momentum, quality, growth, low-volatility
  — the lineage of Fama-French and firms like AQR).
- **Cross-sectional ranking.** Decisions are relative-to-peers-today, not against
  arbitrary fixed thresholds that go stale as markets move.
- **Risk-awareness baked in.** Volatility, beta, max drawdown, correlation, and
  the macro regime all shape sizing and posture — not just expected return.
- **Regime-conditioned posture.** The same scorecard yields a more defensive
  portfolio when the curve inverts or volatility spikes.
- **Auditable, structured decisions.** Every pick carries its dollar amount,
  category, conviction, and the exact factor percentiles behind it.
- **A closed feedback loop.** Every recommendation is logged with its entry price
  and scored against buying SPY on the same day. The dashboard shows **alpha** —
  did the picks beat the index, or not? Most "AI advisors" never check.
- **Engineering robustness.** Graceful fallback if web search is unavailable;
  retry/backoff on transient API errors; tolerant handling of missing data
  (crypto/ETFs lack fundamentals); safe, conflict-resistant automation.

---

## 7. Honest limitations

Sophistication is not a crystal ball. Be clear-eyed:

- **It is not financial advice.** It's research output from a statistical model
  that can be confidently wrong.
- **More factors ≠ guaranteed returns.** Factor investing has long stretches of
  underperformance. The tracking layer exists precisely because rigor doesn't
  guarantee results — it lets you *find out*.
- **Returns are price-only** (dividends excluded) and measured from entry date;
  they're an approximation, not a brokerage statement.
- **Monthly cadence, ~55-ticker universe, no execution.** It suggests; it doesn't
  trade. It can't see assets outside its watchlist.
- **The news and macro reads can be incomplete or misinterpreted.**
- **Survivorship and recency** affect any backtest-free, forward-only record.

The right way to use it: as a disciplined, transparent *starting point* for your
own research — with a track record you can hold it accountable to.

---

## 8. Appendix — architecture

| Module | Role |
|--------|------|
| `factors.py` | Computes technical + fundamental factors, ranks them, builds composites |
| `macro.py` | Macro regime indicators + cross-asset correlation summary |
| `market_research.py` | Weekly: scorecard + macro + web-search briefing |
| `generate_recs.py` | Monthly: applies the rubric, gets the structured recommendation |
| `prompts.py` | The prompts, the output schema, and the markdown renderer |
| `tracking.py` | Ledger of picks + performance scoring vs SPY |
| `send_report.py` | Emails the HTML report |
| `docs/index.html` | The public dashboard (Recommendations / Weekly Research / Track Record) |

**Schedule:** weekly research every Sunday; recommendations on the 1st of each
month — both automated on GitHub Actions, with results committed back to the repo
and rendered on the dashboard.

**Model:** Claude Opus 4.8 for both the weekly briefing and the monthly decision.

*Generated as living documentation of the system's design. If the code changes,
update this doc.*
