# Long Agent - Trades Long Positions Only
# Looks for bullish signals to enter long positions

from typing import Optional, Dict, Any, List
from datetime import datetime
import threading
import time

from config import (
    TradingConfig, AgentType, OrderSide, OrderType, 
    TradeSignal, Position, setup_logging, is_trading_hours,
    ticks_to_points, calculate_dollar_value
)
from tradestation_client import TradeStationClient
from indicators import TechnicalIndicators, IndicatorValues


class LongAgent:
    """
    Trading agent that focuses on LONG positions only.
    
    Entry conditions (bullish signals):
    - EMA fast > EMA slow (uptrend)
    - RSI < 70 (not overbought) and RSI > 30 (recovering from oversold)
    - Price above VWAP
    - MACD histogram positive or turning positive
    - ADX > 20 (trending market)
    
    Exit conditions:
    - Stop loss hit
    - Take profit hit
    - EMA crossover bearish
    - RSI > 80 (extremely overbought)
    """
    
    def __init__(self, config: TradingConfig, client: TradeStationClient):
        self.config = config
        self.client = client
        self.logger = setup_logging("LongAgent")
        
        self.agent_type = AgentType.LONG
        self.is_running = False
        self.current_position: Optional[Position] = None
        self.pending_orders: List[Dict[str, Any]] = []
        
        # Performance tracking
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        # State
        self.last_signal: Optional[TradeSignal] = None
        self.last_indicators: Optional[IndicatorValues] = None
        self.last_price = 0.0
        
        self._lock = threading.Lock()
    
    def analyze_market(self, bars: List[Dict[str, Any]], quote: Dict[str, Any]) -> TradeSignal:
        """Analyze market conditions and generate trading signal"""
        
        # Calculate indicators
        indicators = TechnicalIndicators.calculate_all(bars, self.config)
        self.last_indicators = indicators
        
        # Get current price
        current_price = float(quote.get("Last", 0))
        bid = float(quote.get("Bid", 0))
        ask = float(quote.get("Ask", 0))
        self.last_price = current_price
        
        # Default signal: HOLD
        signal = TradeSignal(
            agent_type=self.agent_type,
            action="HOLD",
            side=OrderSide.BUY,
            quantity=0,
            reason="No clear signal"
        )
        
        # Check if we have a position
        self._update_position()
        
        if self.current_position and self.current_position.quantity > 0:
            # We have a long position - look for exit signals
            signal = self._check_exit_signals(indicators, current_price)
        else:
            # No position - look for entry signals
            signal = self._check_entry_signals(indicators, current_price, ask)
        
        self.last_signal = signal
        return signal
    
    def _check_entry_signals(
        self, 
        indicators: IndicatorValues, 
        current_price: float,
        ask_price: float
    ) -> TradeSignal:
        """Check for bullish entry signals"""
        
        reasons = []
        score = 0.0
        
        # 1. EMA Crossover (Trend)
        if indicators.ema_fast > indicators.ema_slow:
            score += 0.2
            reasons.append("EMA bullish")
        else:
            # Don't enter against the trend
            return TradeSignal(
                agent_type=self.agent_type,
                action="HOLD",
                side=OrderSide.BUY,
                quantity=0,
                reason="EMA bearish - no long entry"
            )
        
        # 2. RSI Conditions
        if indicators.rsi < self.config.RSI_OVERBOUGHT:
            if indicators.rsi > 40:  # Recovering but not overbought
                score += 0.15
                reasons.append(f"RSI favorable ({indicators.rsi:.1f})")
            if 30 < indicators.rsi < 45:  # Bouncing from oversold
                score += 0.15
                reasons.append("RSI oversold bounce")
        else:
            return TradeSignal(
                agent_type=self.agent_type,
                action="HOLD",
                side=OrderSide.BUY,
                quantity=0,
                reason=f"RSI overbought ({indicators.rsi:.1f})"
            )
        
        # 3. VWAP
        if current_price > indicators.vwap:
            score += 0.15
            reasons.append("Above VWAP")
        
        # 4. MACD
        if indicators.macd_histogram > 0:
            score += 0.15
            reasons.append("MACD positive")
        elif indicators.macd > indicators.macd_signal:
            score += 0.1
            reasons.append("MACD bullish crossover")
        
        # 5. ADX (Trend Strength)
        if indicators.adx > 20:
            if indicators.plus_di > indicators.minus_di:
                score += 0.15
                reasons.append(f"ADX trending bullish ({indicators.adx:.1f})")
        
        # 6. Bollinger Bands
        if current_price < indicators.bollinger_middle:
            score += 0.05
            reasons.append("Below BB middle (value)")
        
        # 7. Stochastic
        if indicators.stochastic_k < 80 and indicators.stochastic_k > indicators.stochastic_d:
            score += 0.1
            reasons.append("Stochastic bullish")
        
        # 8. Volume confirmation
        if indicators.current_volume > indicators.volume_sma * 1.2:
            score += 0.05
            reasons.append("Volume above average")
        
        # Decision
        if score >= 0.5:
            # Calculate stop loss and take profit
            atr = indicators.atr if indicators.atr > 0 else ticks_to_points(self.config.STOP_LOSS_TICKS)
            
            stop_loss = ask_price - (atr * 2)
            take_profit = ask_price + (atr * 3)
            
            return TradeSignal(
                agent_type=self.agent_type,
                action="ENTER",
                side=OrderSide.BUY,
                quantity=self.config.DEFAULT_CONTRACTS,
                price=ask_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason=" | ".join(reasons),
                confidence=score
            )
        
        return TradeSignal(
            agent_type=self.agent_type,
            action="HOLD",
            side=OrderSide.BUY,
            quantity=0,
            reason=f"Score too low ({score:.2f}): " + ", ".join(reasons) if reasons else "No signals",
            confidence=score
        )
    
    def _check_exit_signals(
        self,
        indicators: IndicatorValues,
        current_price: float
    ) -> TradeSignal:
        """Check for exit signals when holding a long position"""
        
        if not self.current_position:
            return TradeSignal(
                agent_type=self.agent_type,
                action="HOLD",
                side=OrderSide.SELL,
                quantity=0,
                reason="No position"
            )
        
        entry_price = self.current_position.average_price
        pnl = current_price - entry_price
        pnl_ticks = pnl * 4  # 4 ticks per point
        
        reasons = []
        should_exit = False
        
        # 1. Stop Loss (managed by bracket order, but double-check)
        if pnl_ticks <= -self.config.STOP_LOSS_TICKS:
            should_exit = True
            reasons.append(f"Stop loss hit ({pnl_ticks:.0f} ticks)")
        
        # 2. Take Profit (managed by bracket order, but double-check)
        if pnl_ticks >= self.config.TAKE_PROFIT_TICKS:
            should_exit = True
            reasons.append(f"Take profit hit ({pnl_ticks:.0f} ticks)")
        
        # 3. EMA Bearish Crossover
        if indicators.ema_fast < indicators.ema_slow:
            should_exit = True
            reasons.append("EMA bearish crossover")
        
        # 4. RSI Extremely Overbought
        if indicators.rsi > 80:
            should_exit = True
            reasons.append(f"RSI extremely overbought ({indicators.rsi:.1f})")
        
        # 5. MACD Bearish Crossover with profit
        if indicators.macd < indicators.macd_signal and pnl_ticks > 8:
            should_exit = True
            reasons.append("MACD bearish + profit")
        
        # 6. Price below VWAP with profit
        if current_price < indicators.vwap and pnl_ticks > 4:
            reasons.append("Below VWAP (warning)")
        
        # 7. ADX Trend Reversal
        if indicators.plus_di < indicators.minus_di and pnl_ticks > 0:
            should_exit = True
            reasons.append("ADX trend reversal")
        
        if should_exit:
            return TradeSignal(
                agent_type=self.agent_type,
                action="EXIT",
                side=OrderSide.SELL,
                quantity=abs(self.current_position.quantity),
                reason=" | ".join(reasons)
            )
        
        return TradeSignal(
            agent_type=self.agent_type,
            action="HOLD",
            side=OrderSide.SELL,
            quantity=0,
            reason=f"Holding position (PnL: {pnl_ticks:.0f} ticks)"
        )
    
    def _update_position(self):
        """Update current position from broker"""
        positions = self.client.get_positions()
        
        self.current_position = None
        for pos in positions:
            if pos.symbol == self.config.SYMBOL and pos.side == "Long":
                self.current_position = pos
                break
    
    def execute_signal(self, signal: TradeSignal) -> bool:
        """Execute a trading signal"""
        
        if signal.action == "HOLD":
            return True
        
        # Check daily limits
        if self.daily_trades >= self.config.MAX_DAILY_TRADES:
            self.logger.warning("Max daily trades reached")
            return False
        
        if self.daily_pnl <= -self.config.MAX_DAILY_LOSS:
            self.logger.warning("Max daily loss reached")
            return False
        
        try:
            if signal.action == "ENTER":
                # Place bracket order
                result = self.client.place_bracket_order(
                    symbol=self.config.SYMBOL,
                    quantity=signal.quantity,
                    side=signal.side,
                    stop_loss_price=signal.stop_loss,
                    take_profit_price=signal.take_profit
                )
                
                if result:
                    self.daily_trades += 1
                    self.logger.info(
                        f"LONG ENTRY: {signal.quantity} @ {signal.price:.2f} | "
                        f"SL: {signal.stop_loss:.2f} | TP: {signal.take_profit:.2f} | "
                        f"Reason: {signal.reason}"
                    )
                    return True
                    
            elif signal.action == "EXIT":
                # Flatten position
                result = self.client.flatten_position(self.config.SYMBOL)
                
                if result:
                    self.logger.info(f"LONG EXIT: {signal.reason}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error executing signal: {e}")
            return False
    
    def run_cycle(self) -> Optional[TradeSignal]:
        """Run one analysis cycle"""
        
        if not is_trading_hours(self.config):
            return None
        
        try:
            # Get market data
            bars = self.client.get_bars(
                symbol=self.config.SYMBOL,
                interval=5,
                unit="Minute",
                bars_back=100
            )
            
            quote = self.client.get_quote(self.config.SYMBOL)
            
            if not bars or not quote:
                self.logger.warning("Failed to get market data")
                return None
            
            # Analyze and generate signal
            signal = self.analyze_market(bars, quote)
            
            # Execute if actionable
            if signal.action != "HOLD":
                self.execute_signal(signal)
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Error in run cycle: {e}")
            return None
    
    def start(self):
        """Start the agent"""
        self.is_running = True
        self.logger.info("Long Agent started")
    
    def stop(self):
        """Stop the agent"""
        self.is_running = False
        self.logger.info("Long Agent stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        return {
            "agent_type": self.agent_type.value,
            "is_running": self.is_running,
            "current_position": {
                "quantity": self.current_position.quantity if self.current_position else 0,
                "avg_price": self.current_position.average_price if self.current_position else 0,
                "unrealized_pnl": self.current_position.unrealized_pnl if self.current_position else 0
            },
            "daily_pnl": self.daily_pnl,
            "daily_trades": self.daily_trades,
            "last_signal": {
                "action": self.last_signal.action if self.last_signal else "NONE",
                "reason": self.last_signal.reason if self.last_signal else ""
            },
            "last_price": self.last_price,
            "indicators": {
                "ema_fast": self.last_indicators.ema_fast if self.last_indicators else 0,
                "ema_slow": self.last_indicators.ema_slow if self.last_indicators else 0,
                "rsi": self.last_indicators.rsi if self.last_indicators else 0,
                "macd": self.last_indicators.macd_histogram if self.last_indicators else 0
            }
        }
