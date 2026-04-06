# TQQQ Trading System - TradeStation
# EMA Crossover + TTM Squeeze Strategy
# 2-Level Position Sizing: 1000 or 2000 shares

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import logging

@dataclass
class TradingConfig:
    """TQQQ Trading Configuration with 2-Level Position Sizing"""
    
    # TradeStation API
    API_KEY: str = os.getenv("TS_API_KEY", "")
    API_SECRET: str = os.getenv("TS_API_SECRET", "")
    REFRESH_TOKEN: str = os.getenv("TS_REFRESH_TOKEN", "")
    ACCOUNT_ID: str = os.getenv("TS_ACCOUNT_ID", "")
    
    BASE_URL: str = "https://api.tradestation.com/v3"
    AUTH_URL: str = "https://signin.tradestation.com/oauth/token"
    
    # Symbol
    SYMBOL: str = "TQQQ"
    
    # ==========================================================================
    # 2-LEVEL POSITION SIZING
    # ==========================================================================
    LEVEL_1_SHARES: int = 1000   # Standard position
    LEVEL_2_SHARES: int = 2000   # Strong signal position
    
    # Level 2 requires stronger confirmation
    LEVEL_2_MIN_SCORE: float = 0.70      # Higher score needed
    LEVEL_2_REQUIRES_SQUEEZE_FIRE: bool = True
    LEVEL_2_REQUIRES_MOMENTUM_RISING: bool = True
    LEVEL_2_MIN_ADX: float = 25.0
    
    LEVEL_1_MIN_SCORE: float = 0.50      # Standard threshold
    
    # ==========================================================================
    # RISK MANAGEMENT
    # ==========================================================================
    # Level 1 (1000 shares) - wider stops
    L1_STOP_LOSS_PCT: float = 1.5
    L1_TAKE_PROFIT_PCT: float = 3.0
    
    # Level 2 (2000 shares) - tighter stops due to larger size
    L2_STOP_LOSS_PCT: float = 1.0
    L2_TAKE_PROFIT_PCT: float = 2.0
    
    MAX_DAILY_LOSS: float = 2000.0
    MAX_DAILY_TRADES: int = 10
    MAX_POSITION_VALUE: float = 200000.0
    
    # ==========================================================================
    # INDICATORS
    # ==========================================================================
    EMA_FAST: int = 8
    EMA_SLOW: int = 21
    RSI_PERIOD: int = 14
    RSI_OVERBOUGHT: float = 70.0
    RSI_OVERSOLD: float = 30.0
    ATR_PERIOD: int = 14
    
    # TTM Squeeze
    TTM_BB_PERIOD: int = 20
    TTM_BB_MULT: float = 2.0
    TTM_KC_PERIOD: int = 20
    TTM_KC_MULT: float = 1.5
    
    # ==========================================================================
    # TRADING HOURS
    # ==========================================================================
    TRADING_START_HOUR: int = 9
    TRADING_START_MINUTE: int = 30
    TRADING_END_HOUR: int = 16
    TRADING_END_MINUTE: int = 0
    
    # Bar settings
    BAR_INTERVAL: int = 5
    BAR_UNIT: str = "Minute"
    BARS_BACK: int = 100
    
    CYCLE_INTERVAL: int = 5


class PositionLevel(Enum):
    NONE = 0
    LEVEL_1 = 1   # 1000 shares
    LEVEL_2 = 2   # 2000 shares


class OrderSide(Enum):
    BUY = "Buy"
    SELL = "Sell"
    SELL_SHORT = "SellShort"
    BUY_TO_COVER = "BuyToCover"


class AgentType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class Position:
    symbol: str
    quantity: int
    average_price: float
    market_value: float
    unrealized_pnl: float
    side: str


@dataclass
class TradeSignal:
    agent_type: AgentType
    action: str  # ENTER, EXIT, HOLD
    side: OrderSide
    quantity: int
    level: PositionLevel
    price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    reason: str = ""
    score: float = 0.0


def setup_logging(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    if logger.handlers:
        return logger
    
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(asctime)s | %(name)s | %(message)s', '%H:%M:%S'))
    
    fh = logging.FileHandler(f'tqqq_{name.lower()}.log')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))
    
    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger


def get_shares(level: PositionLevel, config: TradingConfig) -> int:
    if level == PositionLevel.LEVEL_2:
        return config.LEVEL_2_SHARES
    elif level == PositionLevel.LEVEL_1:
        return config.LEVEL_1_SHARES
    return 0


def get_stop_pct(level: PositionLevel, config: TradingConfig) -> float:
    return config.L2_STOP_LOSS_PCT if level == PositionLevel.LEVEL_2 else config.L1_STOP_LOSS_PCT


def get_target_pct(level: PositionLevel, config: TradingConfig) -> float:
    return config.L2_TAKE_PROFIT_PCT if level == PositionLevel.LEVEL_2 else config.L1_TAKE_PROFIT_PCT


def calc_stop(price: float, level: PositionLevel, config: TradingConfig, is_long: bool) -> float:
    pct = get_stop_pct(level, config) / 100
    return round(price * (1 - pct) if is_long else price * (1 + pct), 2)


def calc_target(price: float, level: PositionLevel, config: TradingConfig, is_long: bool) -> float:
    pct = get_target_pct(level, config) / 100
    return round(price * (1 + pct) if is_long else price * (1 - pct), 2)


def calc_pnl_pct(entry: float, current: float, is_long: bool) -> float:
    if entry == 0:
        return 0.0
    return ((current - entry) / entry * 100) if is_long else ((entry - current) / entry * 100)


def calc_pnl_dollars(entry: float, current: float, shares: int, is_long: bool) -> float:
    return (current - entry) * shares if is_long else (entry - current) * shares


def is_market_open(config: TradingConfig) -> bool:
    from datetime import datetime
    import pytz
    
    et = pytz.timezone('US/Eastern')
    now = datetime.now(et)
    
    if now.weekday() >= 5:
        return False
    
    mins = now.hour * 60 + now.minute
    start = config.TRADING_START_HOUR * 60 + config.TRADING_START_MINUTE
    end = config.TRADING_END_HOUR * 60 + config.TRADING_END_MINUTE
    
    return start <= mins < end
