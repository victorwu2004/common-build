# Technical Indicators for TQQQ Trading
# EMA, RSI, ATR, VWAP, ADX, TTM Squeeze

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class Indicators:
    """Calculated indicator values"""
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    rsi: float = 50.0
    atr: float = 0.0
    vwap: float = 0.0
    adx: float = 0.0
    plus_di: float = 0.0
    minus_di: float = 0.0
    
    # TTM Squeeze
    squeeze_on: bool = False
    squeeze_fired: bool = False
    squeeze_momentum: float = 0.0
    momentum_rising: bool = False
    momentum_direction: int = 0  # 1=bullish, -1=bearish, 0=neutral


class TechnicalIndicators:
    """Calculate technical indicators from bar data"""
    
    @staticmethod
    def calculate_all(bars: List[Dict], config) -> Indicators:
        if not bars or len(bars) < 30:
            return Indicators()
        
        closes = np.array([float(b.get("Close", 0)) for b in bars])
        highs = np.array([float(b.get("High", 0)) for b in bars])
        lows = np.array([float(b.get("Low", 0)) for b in bars])
        volumes = np.array([float(b.get("TotalVolume", 0)) for b in bars])
        
        result = Indicators()
        
        # EMAs
        result.ema_fast = TechnicalIndicators._ema(closes, config.EMA_FAST)
        result.ema_slow = TechnicalIndicators._ema(closes, config.EMA_SLOW)
        
        # RSI
        result.rsi = TechnicalIndicators._rsi(closes, config.RSI_PERIOD)
        
        # ATR
        result.atr = TechnicalIndicators._atr(highs, lows, closes, config.ATR_PERIOD)
        
        # VWAP
        result.vwap = TechnicalIndicators._vwap(highs, lows, closes, volumes)
        
        # ADX
        adx, plus_di, minus_di = TechnicalIndicators._adx(highs, lows, closes, 14)
        result.adx = adx
        result.plus_di = plus_di
        result.minus_di = minus_di
        
        # TTM Squeeze
        squeeze = TechnicalIndicators._ttm_squeeze(
            highs, lows, closes,
            config.TTM_BB_PERIOD, config.TTM_BB_MULT,
            config.TTM_KC_PERIOD, config.TTM_KC_MULT
        )
        result.squeeze_on = squeeze["on"]
        result.squeeze_fired = squeeze["fired"]
        result.squeeze_momentum = squeeze["momentum"]
        result.momentum_rising = squeeze["rising"]
        result.momentum_direction = squeeze["direction"]
        
        return result
    
    @staticmethod
    def _ema(data: np.ndarray, period: int) -> float:
        if len(data) < period:
            return float(data[-1]) if len(data) > 0 else 0.0
        
        multiplier = 2 / (period + 1)
        ema = np.mean(data[:period])
        
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        
        return float(ema)
    
    @staticmethod
    def _rsi(closes: np.ndarray, period: int) -> float:
        if len(closes) < period + 1:
            return 50.0
        
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return float(100 - (100 / (1 + rs)))
    
    @staticmethod
    def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
        if len(closes) < period + 1:
            return float(np.mean(highs - lows))
        
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1])
            )
        )
        
        atr = np.mean(tr[:period])
        for i in range(period, len(tr)):
            atr = (atr * (period - 1) + tr[i]) / period
        
        return float(atr)
    
    @staticmethod
    def _vwap(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray) -> float:
        typical = (highs + lows + closes) / 3
        total_vol = np.sum(volumes)
        
        if total_vol == 0:
            return float(closes[-1])
        
        return float(np.sum(typical * volumes) / total_vol)
    
    @staticmethod
    def _adx(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> tuple:
        if len(closes) < period + 1:
            return 20.0, 20.0, 20.0
        
        plus_dm = np.maximum(highs[1:] - highs[:-1], 0)
        minus_dm = np.maximum(lows[:-1] - lows[1:], 0)
        
        plus_dm[plus_dm < minus_dm] = 0
        minus_dm[minus_dm < plus_dm] = 0
        
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1])
            )
        )
        
        atr = np.mean(tr[:period])
        plus_di = np.mean(plus_dm[:period])
        minus_di = np.mean(minus_dm[:period])
        
        for i in range(period, len(tr)):
            atr = (atr * (period - 1) + tr[i]) / period
            plus_di = (plus_di * (period - 1) + plus_dm[i]) / period
            minus_di = (minus_di * (period - 1) + minus_dm[i]) / period
        
        if atr > 0:
            plus_di = (plus_di / atr) * 100
            minus_di = (minus_di / atr) * 100
        
        di_sum = plus_di + minus_di
        dx = abs(plus_di - minus_di) / di_sum * 100 if di_sum > 0 else 0
        
        return float(dx), float(plus_di), float(minus_di)
    
    @staticmethod
    def _ttm_squeeze(
        highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
        bb_period: int, bb_mult: float, kc_period: int, kc_mult: float
    ) -> Dict[str, Any]:
        """Calculate TTM Squeeze indicator"""
        
        result = {"on": False, "fired": False, "momentum": 0.0, "rising": False, "direction": 0}
        
        if len(closes) < max(bb_period, kc_period) + 5:
            return result
        
        # Bollinger Bands
        bb_sma = np.mean(closes[-bb_period:])
        bb_std = np.std(closes[-bb_period:])
        bb_upper = bb_sma + bb_mult * bb_std
        bb_lower = bb_sma - bb_mult * bb_std
        
        # Keltner Channels
        kc_sma = np.mean(closes[-kc_period:])
        tr = np.maximum(
            highs[-kc_period:] - lows[-kc_period:],
            np.maximum(
                np.abs(highs[-kc_period:] - np.roll(closes[-kc_period:], 1)),
                np.abs(lows[-kc_period:] - np.roll(closes[-kc_period:], 1))
            )
        )
        kc_atr = np.mean(tr[1:])
        kc_upper = kc_sma + kc_mult * kc_atr
        kc_lower = kc_sma - kc_mult * kc_atr
        
        # Squeeze detection
        squeeze_on = bb_lower > kc_lower and bb_upper < kc_upper
        
        # Check previous squeeze state for "fired" detection
        if len(closes) >= bb_period + 3:
            prev_closes = closes[-(bb_period + 3):-3]
            prev_sma = np.mean(prev_closes[-bb_period:])
            prev_std = np.std(prev_closes[-bb_period:])
            prev_bb_upper = prev_sma + bb_mult * prev_std
            prev_bb_lower = prev_sma - bb_mult * prev_std
            
            prev_highs = highs[-(kc_period + 3):-3]
            prev_lows = lows[-(kc_period + 3):-3]
            prev_kc_sma = np.mean(prev_closes[-kc_period:])
            prev_tr = np.maximum(prev_highs - prev_lows, 0.01)
            prev_kc_atr = np.mean(prev_tr)
            prev_kc_upper = prev_kc_sma + kc_mult * prev_kc_atr
            prev_kc_lower = prev_kc_sma - kc_mult * prev_kc_atr
            
            prev_squeeze_on = prev_bb_lower > prev_kc_lower and prev_bb_upper < prev_kc_upper
            squeeze_fired = prev_squeeze_on and not squeeze_on
        else:
            squeeze_fired = False
        
        # Momentum (Linear Regression)
        lookback = 20
        if len(closes) >= lookback:
            x = np.arange(lookback)
            y = closes[-lookback:]
            
            # Detrend: value - midline
            highest = np.max(highs[-lookback:])
            lowest = np.min(lows[-lookback:])
            midline = (highest + lowest) / 2
            
            momentum = closes[-1] - midline
            prev_momentum = closes[-2] - ((np.max(highs[-lookback-1:-1]) + np.min(lows[-lookback-1:-1])) / 2)
            
            momentum_rising = abs(momentum) > abs(prev_momentum)
            
            if momentum > 0:
                direction = 1
            elif momentum < 0:
                direction = -1
            else:
                direction = 0
        else:
            momentum = 0.0
            momentum_rising = False
            direction = 0
        
        result["on"] = squeeze_on
        result["fired"] = squeeze_fired
        result["momentum"] = float(momentum)
        result["rising"] = momentum_rising
        result["direction"] = direction
        
        return result
