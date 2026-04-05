# TQQQ Trading System - TradeStation

## 2-Level Position Sizing: 1000 or 2000 Shares

Automated TQQQ trading system using EMA Crossover + TTM Squeeze strategy with intelligent position sizing.

## Position Levels

| Level | Shares | Score Required | Additional Requirements | Stop | Target |
|-------|--------|----------------|------------------------|------|--------|
| **L1** | 1,000 | >= 0.50 | None | 1.5% | 3.0% |
| **L2** | 2,000 | >= 0.70 | Squeeze fired + Momentum rising + ADX > 25 | 1.0% | 2.0% |

### Why Different Risk Parameters?

- **Level 2** uses tighter stops because the position is larger
- A 1% move on 2000 shares = same dollar risk as 1.5% on 1000 shares
- This keeps per-trade risk roughly consistent

## Position Value Examples (at $60/share)

| Level | Shares | Position Value | Stop Loss $ | Target $ |
|-------|--------|----------------|-------------|----------|
| L1 | 1,000 | $60,000 | -$900 | +$1,800 |
| L2 | 2,000 | $120,000 | -$1,200 | +$2,400 |

## Setup

### 1. Set Environment Variables

```powershell
# PowerShell
$env:TS_API_KEY = "your_api_key"
$env:TS_API_SECRET = "your_api_secret"  
$env:TS_REFRESH_TOKEN = "your_refresh_token"
$env:TS_ACCOUNT_ID = "your_account_id"
```

```bash
# Bash
export TS_API_KEY="your_api_key"
export TS_API_SECRET="your_api_secret"
export TS_REFRESH_TOKEN="your_refresh_token"
export TS_ACCOUNT_ID="your_account_id"
```

### 2. Install & Run

```bash
pip install -r requirements.txt
python main.py
```

## Strategy Logic

```
ENTRY SCORING:
═══════════════════════════════════════════════════════════
EMA 8 > EMA 21 (bullish)          +0.25  [REQUIRED]
Squeeze FIRED                      +0.25
Squeeze off (not fired)            +0.10
Momentum positive                  +0.20  [REQUIRED]
Momentum rising                    +0.10
RSI OK (40-70)                     +0.05
Price > VWAP                       +0.05
ADX trending                       +0.05
───────────────────────────────────────────────────────────
Total possible:                    ~0.90

LEVEL DETERMINATION:
═══════════════════════════════════════════════════════════
Score >= 0.70 + Squeeze FIRED + Mom Rising + ADX > 25
    → Level 2: 2000 shares

Score >= 0.50
    → Level 1: 1000 shares

Score < 0.50
    → No trade
```

## Sample Output

```
============================================================
TQQQ TRADING SYSTEM - 2-Level Position Sizing
============================================================
Account: ABC123456
Balance: $150,000.00
Buying Power: $300,000.00
------------------------------------------------------------
Symbol: TQQQ @ $62.50
------------------------------------------------------------
POSITION LEVELS:
  Level 1: 1000 shares ($62,500)
           Stop: 1.5% | Target: 3.0%
           Requires: Score >= 0.5
  Level 2: 2000 shares ($125,000)
           Stop: 1.0% | Target: 2.0%
           Requires: Score >= 0.7 + Squeeze Fire + Mom Rising + ADX>25
------------------------------------------------------------
Strategy: EMA 8/21 + TTM Squeeze
Max Daily Loss: $5,000
Max Trades/Day: 10
============================================================
System started - Press Ctrl+C to stop

--------------------------------------------------
Cycle 10 | TQQQ $62.75
EMA: 62.80/62.45 | Squeeze: FIRED ⚡ | Mom: 0.85 ↑
🟢 LONG [L2]: 2000 shares @ $62.80 ($125,600) | SL: $62.17 (-1.0%) | TP: $64.06 (+2.0%)
```

## Files

| File | Description |
|------|-------------|
| `config.py` | Configuration, levels, risk parameters |
| `tradestation_client.py` | TradeStation API client |
| `indicators.py` | EMA, RSI, ATR, TTM Squeeze |
| `long_agent.py` | Long agent with 2-level sizing |
| `short_agent.py` | Short agent with 2-level sizing |
| `main.py` | Main orchestrator |

## Customization

Edit `config.py` to adjust:

```python
# Position sizes
LEVEL_1_SHARES = 1000
LEVEL_2_SHARES = 2000

# Score thresholds
LEVEL_1_MIN_SCORE = 0.50
LEVEL_2_MIN_SCORE = 0.70

# Level 2 requirements
LEVEL_2_REQUIRES_SQUEEZE_FIRE = True
LEVEL_2_REQUIRES_MOMENTUM_RISING = True
LEVEL_2_MIN_ADX = 25.0

# Risk parameters
L1_STOP_LOSS_PCT = 1.5
L1_TAKE_PROFIT_PCT = 3.0
L2_STOP_LOSS_PCT = 1.0
L2_TAKE_PROFIT_PCT = 2.0
```

## Risk Warning

⚠️ **TQQQ is a 3x leveraged ETF** - amplifies Nasdaq moves by 3x.

- High volatility and risk
- Not suitable for long-term holding
- Paper trade first!

---

MIT License - Use at your own risk.
