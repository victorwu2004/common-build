# ES Dual Agent Trading System

Automated E-mini S&P 500 (ES) futures trading system with two independent agents:
- **Long Agent**: Looks for bullish setups and enters long positions
- **Short Agent**: Looks for bearish setups and enters short positions

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
│              │  TRADESTATION   │                            │
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

## Features

- **Dual Agent System**: Long and Short agents operate independently
- **Technical Analysis**: EMA, RSI, MACD, Bollinger Bands, Stochastic, ADX, VWAP
- **Risk Management**: 
  - Stop loss and take profit orders
  - Maximum daily loss limit
  - Maximum daily trades limit
  - Position coordination between agents
- **Bracket Orders**: Automatic stop loss and take profit placement
- **Logging**: Comprehensive logging to console and file

## Setup

### 1. TradeStation API Credentials

1. Create a TradeStation account (if you don't have one)
2. Go to [TradeStation API](https://api.tradestation.com/)
3. Create an application and get your API credentials
4. Complete OAuth flow to get a refresh token

### 2. Environment Variables

Set these environment variables:

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

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Trading Parameters

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

# Symbol (update for current contract month)
SYMBOL = "ESZ24"  # December 2024
# SYMBOL = "ESH25"  # March 2025
```

## Usage

### Start Trading

```bash
python main.py
```

### Sample Output

```
2024-01-15 09:30:05 | Orchestrator | INFO | ============================================================
2024-01-15 09:30:05 | Orchestrator | INFO | ES Dual Agent Trading System
2024-01-15 09:30:05 | Orchestrator | INFO | ============================================================
2024-01-15 09:30:05 | Orchestrator | INFO | Connected to account: ABC123456
2024-01-15 09:30:05 | Orchestrator | INFO | Account Balance: $50,000.00
2024-01-15 09:30:05 | Orchestrator | INFO | Current ESZ24 price: 4785.50
2024-01-15 09:30:05 | Orchestrator | INFO | Trading system started
2024-01-15 09:30:10 | LongAgent | INFO | LONG ENTRY: 1 @ 4785.75 | SL: 4780.75 | TP: 4795.75
2024-01-15 09:35:15 | ShortAgent | INFO | No short entry - EMA bullish
2024-01-15 09:40:20 | LongAgent | INFO | LONG EXIT: Take profit hit (40 ticks)
```

### Stop Trading

Press `Ctrl+C` to gracefully stop the system.

## Files

| File | Description |
|------|-------------|
| `config.py` | Configuration and shared utilities |
| `tradestation_client.py` | TradeStation API client |
| `indicators.py` | Technical indicators |
| `long_agent.py` | Long trading agent |
| `short_agent.py` | Short trading agent |
| `main.py` | Main orchestrator |
| `requirements.txt` | Python dependencies |

## Trading Logic

### Long Agent Entry Conditions
- EMA(9) > EMA(21) - Uptrend
- RSI between 30-70 - Not extreme
- Price above VWAP - Bullish
- MACD histogram positive - Momentum
- ADX > 20 with +DI > -DI - Trending up

### Short Agent Entry Conditions
- EMA(9) < EMA(21) - Downtrend
- RSI between 30-70 - Not extreme
- Price below VWAP - Bearish
- MACD histogram negative - Momentum
- ADX > 20 with -DI > +DI - Trending down

### Exit Conditions
- Stop loss hit
- Take profit hit
- Trend reversal (EMA crossover)
- Extreme RSI (>80 for longs, <20 for shorts)

## Risk Warning

⚠️ **IMPORTANT**: This is for educational purposes only!

- Futures trading involves substantial risk of loss
- Past performance is not indicative of future results
- Always test with paper trading first
- Never risk money you can't afford to lose
- This system is not financial advice

## Testing

### Paper Trading

Use TradeStation's simulation account:
1. Set `ACCOUNT_ID` to your simulation account
2. The API endpoints work the same for simulation

### Backtesting

For backtesting, you would need to:
1. Download historical data
2. Create a backtesting framework
3. Run the agents against historical data

## Troubleshooting

### Authentication Failed
- Check API credentials
- Ensure refresh token is valid
- May need to re-authenticate through OAuth

### No Trades Executing
- Check trading hours (9:30 AM - 4:00 PM ET)
- Check daily limits not exceeded
- Verify account has sufficient buying power
- Check logs for signal reasons

### Connection Issues
- Check internet connection
- TradeStation API may have rate limits
- API may be down for maintenance

## License

MIT License - Use at your own risk.
