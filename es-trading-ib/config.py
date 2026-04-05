# ES Dual Agent Trading System for Interactive Brokers
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
    """Trading system configuration for Interactive Brokers"""
    
    # IB Connection Settings
    IB_HOST: str = os.getenv("IB_HOST", "127.0.0.1")
    IB_PORT: int = int(os.getenv("IB_PORT", "7497"))  # 7497=TWS Paper, 7496=TWS Live, 4002=Gateway Paper, 4001=Gateway Live
    IB_CLIENT_ID: int = int(os.getenv("IB_CLIENT_ID", "1"))
    
    # Account (leave empty to use first available)
    ACCOUNT_ID: str = os.getenv("IB_ACCOUNT_ID", "")
    
    # ES Futures Contract
    SYMBOL: str = "ES"
    EXCHANGE: str = "CME"
    CURRENCY: str = "USD"
    CONTRACT_MONTH: str = os.getenv("ES_CONTRACT_MONTH", "202506")  # YYYYMM format (June 2025)
    
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
    
    # Trading hours (ES futures - RTH)
    TRADING_START_HOUR: int = 9  # 9:30 AM ET
    TRADING_START_MINUTE: int = 30
    TRADING_END_HOUR: int = 16  # 4:00 PM ET
    TRADING_END_MINUTE: int = 0
    USE_RTH_ONLY: bool = False  # Set True to trade only Regular Trading Hours
    
    # Technical indicators - EMA Crossover
    EMA_FAST: int = 8   # Changed to 8 to match your chart
    EMA_SLOW: int = 21
    RSI_PERIOD: int = 14
    RSI_OVERBOUGHT: float = 70.0
    RSI_OVERSOLD: float = 30.0
    ATR_PERIOD: int = 14
    VWAP_ENABLED: bool = True
    
    # TTM Squeeze parameters (from your chart: TTM_Squeeze(CLOSE, 20, 1.5, 2.0, 1.0))
    TTM_BB_PERIOD: int = 20       # Bollinger Bands period
    TTM_BB_MULT: float = 2.0      # Bollinger Bands std dev multiplier
    TTM_KC_PERIOD: int = 20       # Keltner Channel period
    TTM_KC_MULT: float = 1.5      # Keltner Channel ATR multiplier
    TTM_SQUEEZE_REQUIRED: bool = True  # Require squeeze fire for entry
    
    # Bar settings
    BAR_SIZE: str = "5 mins"  # IB bar size string
    BAR_DURATION: str = "1 D"  # How much history to fetch
    
    # Agent coordination
    AGENT_SYNC_INTERVAL: int = 5  # seconds
    HEARTBEAT_INTERVAL: int = 30  # seconds


class OrderType(Enum):
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP LMT"


class OrderAction(Enum):
    BUY = "BUY"
    SELL = "SELL"


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
    side: OrderAction
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
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
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
    
    # If using RTH only
    if config.USE_RTH_ONLY:
        current_minutes = now.hour * 60 + now.minute
        start_minutes = config.TRADING_START_HOUR * 60 + config.TRADING_START_MINUTE
        end_minutes = config.TRADING_END_HOUR * 60 + config.TRADING_END_MINUTE
        return start_minutes <= current_minutes < end_minutes
    
    # ES futures trade nearly 24 hours (Sunday 6 PM - Friday 5 PM ET)
    # With daily maintenance break 5:00 PM - 6:00 PM ET
    current_hour = now.hour
    
    # Maintenance break
    if current_hour == 17:
        return False
    
    return True
