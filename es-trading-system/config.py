# ES Dual Agent Trading System
# Configuration and Shared Utilities

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import logging

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class TradingConfig:
    """Trading system configuration"""
    
    # TradeStation API credentials
    API_KEY: str = os.getenv("TS_API_KEY", "your_api_key")
    API_SECRET: str = os.getenv("TS_API_SECRET", "your_api_secret")
    REFRESH_TOKEN: str = os.getenv("TS_REFRESH_TOKEN", "your_refresh_token")
    
    # API endpoints
    BASE_URL: str = "https://api.tradestation.com/v3"
    AUTH_URL: str = "https://signin.tradestation.com/oauth/token"
    STREAM_URL: str = "https://api.tradestation.com/v3/marketdata/stream"
    
    # Trading parameters
    SYMBOL: str = "ESZ24"  # ES futures contract (update for current month)
    ACCOUNT_ID: str = os.getenv("TS_ACCOUNT_ID", "your_account_id")
    
    # Position sizing
    MAX_CONTRACTS_LONG: int = 2
    MAX_CONTRACTS_SHORT: int = 2
    DEFAULT_CONTRACTS: int = 1
    
    # Risk management
    STOP_LOSS_TICKS: int = 20  # 20 ticks = 5 points = $250 per contract
    TAKE_PROFIT_TICKS: int = 40  # 40 ticks = 10 points = $500 per contract
    TRAILING_STOP_TICKS: int = 16  # 16 ticks = 4 points
    MAX_DAILY_LOSS: float = 1000.0  # Maximum daily loss in dollars
    MAX_DAILY_TRADES: int = 10
    
    # Trading hours (ES futures)
    TRADING_START_HOUR: int = 9  # 9:30 AM ET
    TRADING_START_MINUTE: int = 30
    TRADING_END_HOUR: int = 16  # 4:00 PM ET
    TRADING_END_MINUTE: int = 0
    
    # Technical indicators
    EMA_FAST: int = 9
    EMA_SLOW: int = 21
    RSI_PERIOD: int = 14
    RSI_OVERBOUGHT: float = 70.0
    RSI_OVERSOLD: float = 30.0
    ATR_PERIOD: int = 14
    VWAP_ENABLED: bool = True
    
    # Agent coordination
    AGENT_SYNC_INTERVAL: int = 5  # seconds
    HEARTBEAT_INTERVAL: int = 30  # seconds


class OrderType(Enum):
    MARKET = "Market"
    LIMIT = "Limit"
    STOP_MARKET = "StopMarket"
    STOP_LIMIT = "StopLimit"


class OrderSide(Enum):
    BUY = "Buy"
    SELL = "Sell"
    BUY_TO_COVER = "BuyToCover"
    SELL_SHORT = "SellShort"


class OrderDuration(Enum):
    DAY = "Day"
    GTC = "GTC"
    GTD = "GTD"
    IOC = "IOC"
    FOK = "FOK"


class AgentType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class Position:
    """Current position information"""
    symbol: str
    quantity: int
    average_price: float
    market_value: float
    unrealized_pnl: float
    side: str  # "Long" or "Short"


@dataclass
class TradeSignal:
    """Trading signal from an agent"""
    agent_type: AgentType
    action: str  # "ENTER", "EXIT", "HOLD"
    side: OrderSide
    quantity: int
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: str = ""
    confidence: float = 0.0


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(name: str) -> logging.Logger:
    """Configure logging for the trading system"""
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    
    # File handler
    file_handler = logging.FileHandler(f'trading_{name}.log')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def ticks_to_points(ticks: int) -> float:
    """Convert ticks to points for ES futures (4 ticks = 1 point)"""
    return ticks / 4.0


def points_to_ticks(points: float) -> int:
    """Convert points to ticks for ES futures"""
    return int(points * 4)


def calculate_dollar_value(ticks: int, contracts: int = 1) -> float:
    """Calculate dollar value for ES futures ($12.50 per tick per contract)"""
    return ticks * 12.50 * contracts


def is_trading_hours(config: TradingConfig) -> bool:
    """Check if current time is within trading hours"""
    from datetime import datetime
    import pytz
    
    et = pytz.timezone('US/Eastern')
    now = datetime.now(et)
    
    # Skip weekends
    if now.weekday() >= 5:
        return False
    
    current_minutes = now.hour * 60 + now.minute
    start_minutes = config.TRADING_START_HOUR * 60 + config.TRADING_START_MINUTE
    end_minutes = config.TRADING_END_HOUR * 60 + config.TRADING_END_MINUTE
    
    return start_minutes <= current_minutes < end_minutes
