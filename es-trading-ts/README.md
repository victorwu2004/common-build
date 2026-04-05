# ES Dual Agent Trading System - TradeStation
## EMA Crossover + TTM Squeeze Strategy

Automated E-mini S&P 500 (ES) futures trading system for TradeStation API.

This system implements **John Carter's TTM Squeeze** combined with **EMA Crossover** signals.

Two independent agents:
- **Long Agent**: Enters when EMA crosses bullish AND squeeze fires with positive momentum
- **Short Agent**: Enters when EMA crosses bearish AND squeeze fires with negative momentum

## Strategy Logic

```
┌─────────────────────────────────────────────────────────────┐
│                     TTM SQUEEZE + EMA                        │
│                                                              │
│  SQUEEZE ON (Red dots)     SQUEEZE FIRES (Green dots)       │
│  ════════════════════      ══════════════════════════       │
│  • Low volatility          • Volatility expanding            │
│  • BB inside KC            • BB outside KC                   │
│  • Consolidation           • BREAKOUT IMMINENT               │
│  • NO ENTRY                • CHECK MOMENTUM + EMA            │
│                                                              │
│  LONG ENTRY:                SHORT ENTRY:                     │
│  ───────────                ────────────                     │
│  • EMA 8 > EMA 21          • EMA 8 < EMA 21                  │
│  • Squeeze fired/off       • Squeeze fired/off               │
│  • Momentum positive       • Momentum negative               │
│  • Momentum rising         • Momentum rising (in magnitude) │
└─────────────────────────────────────────────────────────────┘
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TRADING ORCHESTRATOR                      │
│                                                              │
│  ┌─────────────────────┐    ┌─────────────────────┐        │
│  │     LONG AGENT      │    │     SHORT AGENT     │        │
│  │                     │    │                     │        │
│  │ • EMA 8 > EMA 21    │    │ • EMA 8 < EMA 21    │        │
│  │ • Squeeze FIRED     │    │ • Squeeze FIRED     │        │
│  │ • Momentum +        │    │ • Momentum -        │        │
│  │ • Momentum Rising   │    │ • Momentum Rising   │        │
│  └─────────────────────┘    └─────────────────────┘        │
│              │                        │                     │
│              └────────┬───────────────┘                     │
│                       │                                      │
│              ┌────────▼────────┐                            │
│              │   TRADESTATION  │                            │
│              │     CLIENT      │                            │
│              └────────┬────────┘                            │
│                       │                                      │
└───────────────────────┼──────────────────────────────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │  TRADESTATION   │
              │      API        │
              └─────────────────┘
```

## Prerequisites

### 1. TradeStation Account
- TradeStation brokerage account
- Futures trading permissions for CME

### 2. TradeStation API Access
1. Log in to your TradeStation account
2. Go to [TradeStation API](https://api.tradestation.com/)
3. Create an application to get API credentials
4. Complete OAuth flow to get a refresh token

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

```powershell
# PowerShell
$env:TS_API_KEY = "your_api_key"
$env:TS_API_SECRET = "your_api_secret"
$env:TS_REFRESH_TOKEN = "your_refresh_token"
$env:TS_ACCOUNT_ID = "your_account_id"
$env:TS_SYMBOL = "ESM25"  # Current contract month
```

```bash
# Bash
export TS_API_KEY="your_api_key"
export TS_API_SECRET="your_api_secret"
export TS_REFRESH_TOKEN="your_refresh_token"
export TS_ACCOUNT_ID="your_account_id"
export TS_SYMBOL="ESM25"
```

### 3. ES Contract Months

ES futures expire quarterly. Update `SYMBOL` accordingly:

| Month | Code | Symbol Example |
|-------|------|----------------|
| March | H | ESH25 |
| June | M | ESM25 |
| September | U | ESU25 |
| December | Z | ESZ25 |

### 4. Run the System

```bash
python main.py
```

## Configuration Options

Edit `config.py` to customize:

```python
# Symbol
SYMBOL = "ESM25"  # June 2025 contract

# Position sizing
MAX_CONTRACTS_LONG = 2
MAX_CONTRACTS_SHORT = 2
DEFAULT_CONTRACTS = 1

# Risk management
STOP_LOSS_TICKS = 20      # 5 points = $250/contract
TAKE_PROFIT_TICKS = 40    # 10 points = $500/contract
MAX_DAILY_LOSS = 1000.0   # Stop trading after losing $1000
MAX_DAILY_TRADES = 10

# EMA Crossover settings (matching your chart)
EMA_FAST = 8              # Fast EMA period
EMA_SLOW = 21             # Slow EMA period

# TTM Squeeze parameters (from your chart)
TTM_BB_PERIOD = 20        # Bollinger Bands period
TTM_BB_MULT = 2.0         # Bollinger Bands std dev multiplier
TTM_KC_PERIOD = 20        # Keltner Channel period
TTM_KC_MULT = 1.5         # Keltner Channel ATR multiplier
TTM_SQUEEZE_REQUIRED = True  # Require squeeze fire for entry

# Trading hours
USE_RTH_ONLY = False      # True = 9:30 AM - 4:00 PM ET only

# Bar settings
BAR_INTERVAL = 5          # 5-minute bars
BAR_UNIT = "Minute"
```

## Files

| File | Description |
|------|-------------|
| `config.py` | Configuration and shared utilities |
| `tradestation_client.py` | TradeStation API client |
| `indicators.py` | Technical indicators (EMA, RSI, TTM Squeeze, etc.) |
| `long_agent.py` | Long trading agent |
| `short_agent.py` | Short trading agent |
| `main.py` | Main orchestrator |
| `requirements.txt` | Python dependencies |

## Trading Logic

### TTM Squeeze Explained

The TTM Squeeze detects periods of low volatility (consolidation) that precede big moves:

| Indicator State | Meaning |
|-----------------|---------|
| **Squeeze ON** (red dots) | Bollinger Bands inside Keltner Channels = low volatility |
| **Squeeze OFF** (green dots) | BB outside KC = volatility expanding |
| **Squeeze FIRED** | Transition from ON → OFF = breakout imminent! |
| **Momentum +** (cyan bars) | Bullish momentum |
| **Momentum -** (red bars) | Bearish momentum |
| **Momentum Rising** | Bars getting taller = momentum increasing |

### Long Agent Entry Conditions
1. **EMA 8 > EMA 21** - Bullish trend (REQUIRED)
2. **Squeeze has fired** - Was ON, now OFF (REQUIRED if configured)
3. **Momentum positive** - Histogram above zero (REQUIRED)
4. **Momentum rising** - Bars getting taller (bonus points)
5. RSI not overbought, above VWAP, ADX confirms (optional boosters)

### Short Agent Entry Conditions
1. **EMA 8 < EMA 21** - Bearish trend (REQUIRED)
2. **Squeeze has fired** - Was ON, now OFF (REQUIRED if configured)
3. **Momentum negative** - Histogram below zero (REQUIRED)
4. **Momentum rising** - Bars getting taller downward (bonus points)
5. RSI not oversold, below VWAP, ADX confirms (optional boosters)

### Exit Conditions
- Stop loss hit (ATR-based, via bracket order)
- Take profit hit (ATR-based, via bracket order)
- EMA crossover reversal
- Extreme RSI (>80 for longs, <20 for shorts)
- Momentum reversal with profit

## Sample Output

```
2025-04-05 09:30:05 | Orchestrator | INFO | ======================================================================
2025-04-05 09:30:05 | Orchestrator | INFO | ES Dual Agent Trading System - TradeStation
2025-04-05 09:30:05 | Orchestrator | INFO | Strategy: EMA Crossover + TTM Squeeze
2025-04-05 09:30:05 | Orchestrator | INFO | ======================================================================
2025-04-05 09:30:06 | TSClient | INFO | Successfully authenticated with TradeStation
2025-04-05 09:30:06 | Orchestrator | INFO | Connected to account: ABC123456
2025-04-05 09:30:07 | Orchestrator | INFO | Current ESM25 price: 5285.50
2025-04-05 09:30:07 | Orchestrator | INFO | Trading system started
2025-04-05 09:30:12 | Orchestrator | INFO | --------------------------------------------------
2025-04-05 09:30:12 | Orchestrator | INFO | Cycle: 10 | Price: 5286.25
2025-04-05 09:30:12 | Orchestrator | INFO | Squeeze: OFF FIRED! | Momentum: 15.32 ↑
2025-04-05 09:30:12 | LongAgent | INFO | LONG ENTRY: 1 @ 5286.50 | SL: 5281.50 | TP: 5296.50 | 
    Reason: EMA8x21 bullish | Squeeze FIRED | Momentum bullish (15.32) | Momentum rising
```

## Troubleshooting

### Authentication Issues

**Error: "Authentication failed"**
- Check API credentials are correct
- Refresh token may have expired - re-authenticate via OAuth
- Verify API key has trading permissions

### No Trades Executing

- Check trading hours (ES trades nearly 24h, but has maintenance break 5-6 PM ET)
- Verify daily limits not exceeded
- Check account has sufficient buying power
- Look at logs for signal reasons (squeeze may still be ON)

### Market Data Issues

**Error: "Failed to get bars"**
- Verify symbol is correct and contract hasn't expired
- Check TradeStation API status
- May be rate limited - reduce request frequency

## API Documentation

- TradeStation API: https://api.tradestation.com/docs/

## Risk Warning

⚠️ **IMPORTANT**: This is for educational purposes only!

- Futures trading involves substantial risk of loss
- ES futures have a tick value of $12.50 and multiplier of $50
- One point move = $50 per contract
- Past performance is not indicative of future results
- Always test with paper/simulation trading first
- Never risk money you can't afford to lose
- This system is not financial advice

## Paper Trading

**Strongly recommended** - Test with TradeStation simulation account first:

1. Use your simulation account credentials
2. The API endpoints work the same for simulation
3. Monitor for at least 1-2 weeks before going live

## License

MIT License - Use at your own risk.
