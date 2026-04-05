# ES Dual Agent Trading System - Interactive Brokers
## EMA Crossover + TTM Squeeze Strategy

Automated E-mini S&P 500 (ES) futures trading system for Interactive Brokers using the `ib_insync` library.

This system implements **John Carter's TTM Squeeze** combined with **EMA Crossover** signals - the same strategy visible in your ThinkOrSwim chart.

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
│  │ • EMA Crossover ↑   │    │ • EMA Crossover ↓   │        │
│  │ • RSI Oversold      │    │ • RSI Overbought    │        │
│  │ • Price > VWAP      │    │ • Price < VWAP      │        │
│  │ • MACD Bullish      │    │ • MACD Bearish      │        │
│  │ • ADX Trend Up      │    │ • ADX Trend Down    │        │
│  └─────────────────────┘    └─────────────────────┘        │
│              │                        │                     │
│              └────────┬───────────────┘                     │
│                       │                                      │
│              ┌────────▼────────┐                            │
│              │    IB CLIENT    │                            │
│              │   (ib_insync)   │                            │
│              └────────┬────────┘                            │
│                       │                                      │
└───────────────────────┼──────────────────────────────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │  TWS / Gateway  │
              │   (localhost)   │
              └─────────────────┘
```

## Prerequisites

### 1. Interactive Brokers Account
- Live or Paper trading account
- Futures trading permissions for CME

### 2. TWS or IB Gateway
Download and install one of:
- **Trader Workstation (TWS)**: Full trading platform
- **IB Gateway**: Lightweight API-only connection

Download: https://www.interactivebrokers.com/en/trading/tws.php

### 3. API Settings in TWS/Gateway

1. Open TWS or IB Gateway
2. Go to **File** → **Global Configuration** (or **Edit** → **Global Configuration**)
3. Navigate to **API** → **Settings**
4. Enable:
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Allow connections from localhost only
   - ✅ Read-Only API (disable this for live trading)
5. Set Socket port:
   - **7497** = TWS Paper Trading
   - **7496** = TWS Live Trading
   - **4002** = Gateway Paper Trading
   - **4001** = Gateway Live Trading

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Connection

Edit `config.py` or set environment variables:

```python
# Connection settings
IB_HOST = "127.0.0.1"
IB_PORT = 7497  # 7497=TWS Paper, 7496=TWS Live
IB_CLIENT_ID = 1

# Contract settings
SYMBOL = "ES"
CONTRACT_MONTH = "202506"  # YYYYMM format
```

Or use environment variables:

```bash
# Linux/Mac
export IB_HOST="127.0.0.1"
export IB_PORT="7497"
export IB_CLIENT_ID="1"
export ES_CONTRACT_MONTH="202506"

# Windows PowerShell
$env:IB_HOST = "127.0.0.1"
$env:IB_PORT = "7497"
$env:IB_CLIENT_ID = "1"
$env:ES_CONTRACT_MONTH = "202506"
```

### 3. ES Contract Months

ES futures expire quarterly. Update `CONTRACT_MONTH` accordingly:

| Month | Code | Example |
|-------|------|---------|
| March | H | 202503 |
| June | M | 202506 |
| September | U | 202509 |
| December | Z | 202512 |

### 4. Run the System

1. **Start TWS or IB Gateway** and log in
2. **Run the trading system**:

```bash
python main.py
```

## Configuration Options

Edit `config.py` to customize:

```python
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

# TTM Squeeze parameters (from your chart: TTM_Squeeze(CLOSE, 20, 1.5, 2.0, 1.0))
TTM_BB_PERIOD = 20        # Bollinger Bands period
TTM_BB_MULT = 2.0         # Bollinger Bands std dev multiplier
TTM_KC_PERIOD = 20        # Keltner Channel period
TTM_KC_MULT = 1.5         # Keltner Channel ATR multiplier
TTM_SQUEEZE_REQUIRED = True  # Require squeeze fire for entry

# Trading hours
USE_RTH_ONLY = False      # True = 9:30 AM - 4:00 PM ET only

# Bar settings
BAR_SIZE = "5 mins"       # Candle size for analysis
```

## Files

| File | Description |
|------|-------------|
| `config.py` | Configuration and shared utilities |
| `ib_client.py` | Interactive Brokers client (ib_insync wrapper) |
| `indicators.py` | Technical indicators |
| `long_agent.py` | Long trading agent |
| `short_agent.py` | Short trading agent |
| `main.py` | Main orchestrator |
| `requirements.txt` | Python dependencies |

## Trading Logic

### TTM Squeeze Explained

The TTM Squeeze detects periods of low volatility (consolidation) that precede big moves:

| Indicator State | Meaning |
|-----------------|---------|
| **Squeeze ON** (red dots) | Bollinger Bands inside Keltner Channels = low volatility, consolidation |
| **Squeeze OFF** (green dots) | BB outside KC = volatility expanding, potential breakout |
| **Squeeze FIRED** | Transition from ON → OFF = breakout imminent! |
| **Momentum +** (cyan bars) | Bullish momentum |
| **Momentum -** (red bars) | Bearish momentum |
| **Momentum Rising** | Bars getting taller = momentum increasing |

### Long Agent Entry Conditions
1. **EMA 8 > EMA 21** - Bullish trend (REQUIRED)
2. **Squeeze has fired** - Was ON, now OFF (REQUIRED if `TTM_SQUEEZE_REQUIRED=True`)
3. **Momentum positive** - Histogram above zero (REQUIRED)
4. **Momentum rising** - Bars getting taller (bonus points)
5. RSI not overbought, above VWAP, ADX confirms (optional boosters)

### Short Agent Entry Conditions
1. **EMA 8 < EMA 21** - Bearish trend (REQUIRED)
2. **Squeeze has fired** - Was ON, now OFF (REQUIRED if `TTM_SQUEEZE_REQUIRED=True`)
3. **Momentum negative** - Histogram below zero (REQUIRED)
4. **Momentum rising** - Bars getting taller downward (bonus points)
5. RSI not oversold, below VWAP, ADX confirms (optional boosters)

### Exit Conditions
- Stop loss hit (ATR-based)
- Take profit hit (ATR-based)
- EMA crossover reversal
- Extreme RSI (>80 for longs, <20 for shorts)

## Order Types

The system uses:
- **Bracket Orders**: Entry with attached stop loss and take profit
- **OCO Orders**: One-Cancels-Other for exit management
- **Market Orders**: For entries and emergency exits

## Sample Output

```
2025-04-04 09:30:05 | Orchestrator | INFO | ============================================================
2025-04-04 09:30:05 | Orchestrator | INFO | ES Dual Agent Trading System - Interactive Brokers
2025-04-04 09:30:05 | Orchestrator | INFO | ============================================================
2025-04-04 09:30:06 | IBClient | INFO | Connecting to IB at 127.0.0.1:7497 (clientId=1)
2025-04-04 09:30:06 | IBClient | INFO | Connected to account: DU123456
2025-04-04 09:30:06 | IBClient | INFO | ES contract qualified: ESM5
2025-04-04 09:30:07 | Orchestrator | INFO | Net Liquidation: $100,000.00
2025-04-04 09:30:07 | Orchestrator | INFO | Current ES price: 5285.50
2025-04-04 09:30:07 | Orchestrator | INFO | Trading system started
2025-04-04 09:30:12 | LongAgent | INFO | LONG ENTRY: 1 @ MKT | SL: 5280.50 | TP: 5295.50
2025-04-04 09:35:15 | ShortAgent | INFO | No short entry - EMA bullish
```

## Troubleshooting

### Connection Issues

**Error: "Connection refused"**
- Make sure TWS/Gateway is running
- Check the port number matches your TWS settings
- Verify "Enable ActiveX and Socket Clients" is checked

**Error: "Client ID already in use"**
- Change `IB_CLIENT_ID` to a different number
- Or close other applications connected to IB

### Market Data Issues

**Error: "No market data"**
- Ensure you have market data subscriptions for CME futures
- Check if it's outside trading hours
- Verify the contract month is correct

### Order Issues

**Error: "Order rejected"**
- Check account has sufficient margin
- Verify futures trading permissions
- Ensure contract is tradeable (not expired)

## API Documentation

- ib_insync: https://ib-insync.readthedocs.io/
- IB API: https://interactivebrokers.github.io/tws-api/

## Risk Warning

⚠️ **IMPORTANT**: This is for educational purposes only!

- Futures trading involves substantial risk of loss
- ES futures have a tick value of $12.50 and multiplier of $50
- One point move = $50 per contract
- Past performance is not indicative of future results
- Always test with paper trading first
- Never risk money you can't afford to lose
- This system is not financial advice

## Paper Trading

**Strongly recommended** - Test with IB Paper Trading account first:

1. Log in to TWS with your paper trading credentials
2. Use port **7497** (TWS Paper) or **4002** (Gateway Paper)
3. Trade with simulated money
4. Monitor for at least 1-2 weeks before going live

## License

MIT License - Use at your own risk.
