# Technical Indicators for Trading Signals

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class IndicatorValues:
    """Container for calculated indicator values"""
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    rsi: float = 50.0
    atr: float = 0.0
    vwap: float = 0.0
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_histogram: float = 0.0
    bollinger_upper: float = 0.0
    bollinger_middle: float = 0.0
    bollinger_lower: float = 0.0
    stochastic_k: float = 50.0
    stochastic_d: float = 50.0
    adx: float = 0.0
    plus_di: float = 0.0
    minus_di: float = 0.0
    volume_sma: float = 0.0
    current_volume: float = 0.0


class TechnicalIndicators:
    """Calculate technical indicators from price data"""
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return [0.0] * len(prices)
        
        ema = []
        multiplier = 2 / (period + 1)
        
        # Start with SMA for first EMA value
        sma = sum(prices[:period]) / period
        ema.extend([0.0] * (period - 1))
        ema.append(sma)
        
        # Calculate EMA for remaining values
        for price in prices[period:]:
            new_ema = (price * multiplier) + (ema[-1] * (1 - multiplier))
            ema.append(new_ema)
        
        return ema
    
    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> List[float]:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return [0.0] * len(prices)
        
        sma = []
        for i in range(len(prices)):
            if i < period - 1:
                sma.append(0.0)
            else:
                sma.append(sum(prices[i-period+1:i+1]) / period)
        
        return sma
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return [50.0] * len(prices)
        
        rsi = [50.0] * period
        
        # Calculate price changes
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        
        # Separate gains and losses
        gains = [max(0, c) for c in changes]
        losses = [abs(min(0, c)) for c in changes]
        
        # Initial averages
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        # Calculate RSI
        for i in range(period, len(changes)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                rsi.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi.append(100 - (100 / (1 + rs)))
        
        return rsi
    
    @staticmethod
    def calculate_atr(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14
    ) -> List[float]:
        """Calculate Average True Range"""
        if len(highs) < period + 1:
            return [0.0] * len(highs)
        
        tr = []
        for i in range(len(highs)):
            if i == 0:
                tr.append(highs[i] - lows[i])
            else:
                tr1 = highs[i] - lows[i]
                tr2 = abs(highs[i] - closes[i-1])
                tr3 = abs(lows[i] - closes[i-1])
                tr.append(max(tr1, tr2, tr3))
        
        # Calculate ATR using EMA method
        atr = [0.0] * (period - 1)
        atr.append(sum(tr[:period]) / period)
        
        for i in range(period, len(tr)):
            atr.append((atr[-1] * (period - 1) + tr[i]) / period)
        
        return atr
    
    @staticmethod
    def calculate_vwap(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float]
    ) -> List[float]:
        """Calculate Volume Weighted Average Price"""
        if not volumes or len(volumes) == 0:
            return closes.copy()
        
        vwap = []
        cumulative_volume = 0.0
        cumulative_tp_volume = 0.0
        
        for i in range(len(closes)):
            typical_price = (highs[i] + lows[i] + closes[i]) / 3
            cumulative_volume += volumes[i]
            cumulative_tp_volume += typical_price * volumes[i]
            
            if cumulative_volume > 0:
                vwap.append(cumulative_tp_volume / cumulative_volume)
            else:
                vwap.append(closes[i])
        
        return vwap
    
    @staticmethod
    def calculate_macd(
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Tuple[List[float], List[float], List[float]]:
        """Calculate MACD, Signal, and Histogram"""
        ema_fast = TechnicalIndicators.calculate_ema(prices, fast_period)
        ema_slow = TechnicalIndicators.calculate_ema(prices, slow_period)
        
        macd = [f - s for f, s in zip(ema_fast, ema_slow)]
        
        # Calculate signal line (EMA of MACD)
        signal = TechnicalIndicators.calculate_ema(macd, signal_period)
        
        # Calculate histogram
        histogram = [m - s for m, s in zip(macd, signal)]
        
        return macd, signal, histogram
    
    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Tuple[List[float], List[float], List[float]]:
        """Calculate Bollinger Bands (upper, middle, lower)"""
        sma = TechnicalIndicators.calculate_sma(prices, period)
        
        upper = []
        lower = []
        
        for i in range(len(prices)):
            if i < period - 1:
                upper.append(0.0)
                lower.append(0.0)
            else:
                std = np.std(prices[i-period+1:i+1])
                upper.append(sma[i] + (std_dev * std))
                lower.append(sma[i] - (std_dev * std))
        
        return upper, sma, lower
    
    @staticmethod
    def calculate_stochastic(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        k_period: int = 14,
        d_period: int = 3
    ) -> Tuple[List[float], List[float]]:
        """Calculate Stochastic Oscillator (%K and %D)"""
        if len(closes) < k_period:
            return [50.0] * len(closes), [50.0] * len(closes)
        
        k_values = []
        
        for i in range(len(closes)):
            if i < k_period - 1:
                k_values.append(50.0)
            else:
                highest_high = max(highs[i-k_period+1:i+1])
                lowest_low = min(lows[i-k_period+1:i+1])
                
                if highest_high - lowest_low == 0:
                    k_values.append(50.0)
                else:
                    k = 100 * (closes[i] - lowest_low) / (highest_high - lowest_low)
                    k_values.append(k)
        
        # %D is SMA of %K
        d_values = TechnicalIndicators.calculate_sma(k_values, d_period)
        
        return k_values, d_values
    
    @staticmethod
    def calculate_adx(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14
    ) -> Tuple[List[float], List[float], List[float]]:
        """Calculate ADX, +DI, and -DI"""
        if len(closes) < period + 1:
            return [0.0] * len(closes), [0.0] * len(closes), [0.0] * len(closes)
        
        # Calculate True Range
        tr = []
        plus_dm = []
        minus_dm = []
        
        for i in range(1, len(closes)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i-1])
            tr3 = abs(lows[i] - closes[i-1])
            tr.append(max(tr1, tr2, tr3))
            
            up_move = highs[i] - highs[i-1]
            down_move = lows[i-1] - lows[i]
            
            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0)
            
            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0)
        
        # Smooth using Wilder's method
        atr = [0.0]
        smooth_plus_dm = [0.0]
        smooth_minus_dm = [0.0]
        
        # Initial values
        atr.append(sum(tr[:period]))
        smooth_plus_dm.append(sum(plus_dm[:period]))
        smooth_minus_dm.append(sum(minus_dm[:period]))
        
        for i in range(period, len(tr)):
            atr.append(atr[-1] - (atr[-1] / period) + tr[i])
            smooth_plus_dm.append(smooth_plus_dm[-1] - (smooth_plus_dm[-1] / period) + plus_dm[i])
            smooth_minus_dm.append(smooth_minus_dm[-1] - (smooth_minus_dm[-1] / period) + minus_dm[i])
        
        # Calculate +DI and -DI
        plus_di = []
        minus_di = []
        
        for i in range(len(atr)):
            if atr[i] == 0:
                plus_di.append(0.0)
                minus_di.append(0.0)
            else:
                plus_di.append(100 * smooth_plus_dm[i] / atr[i])
                minus_di.append(100 * smooth_minus_dm[i] / atr[i])
        
        # Calculate DX and ADX
        dx = []
        for i in range(len(plus_di)):
            if plus_di[i] + minus_di[i] == 0:
                dx.append(0.0)
            else:
                dx.append(100 * abs(plus_di[i] - minus_di[i]) / (plus_di[i] + minus_di[i]))
        
        # ADX is smoothed DX
        adx = TechnicalIndicators.calculate_ema(dx, period)
        
        # Pad to match original length
        padding = [0.0]
        
        return padding + adx, padding + plus_di, padding + minus_di
    
    @classmethod
    def calculate_all(
        cls,
        bars: List[Dict[str, Any]],
        config: Any
    ) -> IndicatorValues:
        """Calculate all indicators from bar data"""
        if not bars or len(bars) < 50:
            return IndicatorValues()
        
        # Extract OHLCV data
        opens = [float(bar.get("Open", 0)) for bar in bars]
        highs = [float(bar.get("High", 0)) for bar in bars]
        lows = [float(bar.get("Low", 0)) for bar in bars]
        closes = [float(bar.get("Close", 0)) for bar in bars]
        volumes = [float(bar.get("TotalVolume", 0)) for bar in bars]
        
        # Calculate indicators
        ema_fast = cls.calculate_ema(closes, config.EMA_FAST)
        ema_slow = cls.calculate_ema(closes, config.EMA_SLOW)
        rsi = cls.calculate_rsi(closes, config.RSI_PERIOD)
        atr = cls.calculate_atr(highs, lows, closes, config.ATR_PERIOD)
        vwap = cls.calculate_vwap(highs, lows, closes, volumes)
        macd, macd_signal, macd_histogram = cls.calculate_macd(closes)
        bb_upper, bb_middle, bb_lower = cls.calculate_bollinger_bands(closes)
        stoch_k, stoch_d = cls.calculate_stochastic(highs, lows, closes)
        adx, plus_di, minus_di = cls.calculate_adx(highs, lows, closes)
        volume_sma = cls.calculate_sma(volumes, 20)
        
        # Return latest values
        return IndicatorValues(
            ema_fast=ema_fast[-1] if ema_fast else 0.0,
            ema_slow=ema_slow[-1] if ema_slow else 0.0,
            rsi=rsi[-1] if rsi else 50.0,
            atr=atr[-1] if atr else 0.0,
            vwap=vwap[-1] if vwap else 0.0,
            macd=macd[-1] if macd else 0.0,
            macd_signal=macd_signal[-1] if macd_signal else 0.0,
            macd_histogram=macd_histogram[-1] if macd_histogram else 0.0,
            bollinger_upper=bb_upper[-1] if bb_upper else 0.0,
            bollinger_middle=bb_middle[-1] if bb_middle else 0.0,
            bollinger_lower=bb_lower[-1] if bb_lower else 0.0,
            stochastic_k=stoch_k[-1] if stoch_k else 50.0,
            stochastic_d=stoch_d[-1] if stoch_d else 50.0,
            adx=adx[-1] if adx else 0.0,
            plus_di=plus_di[-1] if plus_di else 0.0,
            minus_di=minus_di[-1] if minus_di else 0.0,
            volume_sma=volume_sma[-1] if volume_sma else 0.0,
            current_volume=volumes[-1] if volumes else 0.0
        )
