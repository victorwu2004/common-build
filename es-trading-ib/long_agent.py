# Long Agent for Interactive Brokers
# Trades Long Positions Only

from typing import Optional, Dict, Any, List
from datetime import datetime
import threading

from config import (
    TradingConfig, AgentType, OrderAction,
    TradeSignal, Position, setup_logging, is_trading_hours,
    ticks_to_points, calculate_dollar_value
)
from ib_client import IBClient
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
    
    def __init__(self, config: TradingConfig, client: IBClient):
        self.config = config
        self.client = client
        self.logger = setup_logging("LongAgent")
        
        self.agent_type = AgentType.LONG
        self.is_running = False
        self.current_position: Optional[Position] = None
        self.active_orders: List[Any] = []
        
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
            side=OrderAction.BUY,
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
        """
        Check for bullish entry signals using EMA Crossover + TTM Squeeze strategy.
        
        Entry conditions:
        1. EMA 8 > EMA 21 (bullish trend)
        2. TTM Squeeze has fired (squeeze off) OR momentum is bullish
        3. Squeeze momentum is positive (bullish)
        4. Momentum is rising (increasing)
        """
        
        reasons = []
        score = 0.0
        
        # =================================================================
        # PRIMARY FILTER: EMA Crossover (REQUIRED)
        # =================================================================
        if indicators.ema_fast > indicators.ema_slow:
            score += 0.25
            reasons.append(f"EMA{self.config.EMA_FAST}x{self.config.EMA_SLOW} bullish")
        else:
            return TradeSignal(
                agent_type=self.agent_type,
                action="HOLD",
                side=OrderAction.BUY,
                quantity=0,
                reason=f"EMA bearish ({indicators.ema_fast:.2f} < {indicators.ema_slow:.2f})"
            )
        
        # =================================================================
        # TTM SQUEEZE CONDITIONS
        # =================================================================
        
        # Check squeeze state
        if self.config.TTM_SQUEEZE_REQUIRED:
            # Squeeze must have fired (was on, now off) for entry
            if indicators.squeeze_fired:
                score += 0.25
                reasons.append("Squeeze FIRED")
            elif not indicators.squeeze_on:
                # Squeeze is off but didn't just fire - still okay if momentum confirms
                score += 0.1
                reasons.append("Squeeze off")
            else:
                # Squeeze is still on - wait for it to fire
                return TradeSignal(
                    agent_type=self.agent_type,
                    action="HOLD",
                    side=OrderAction.BUY,
                    quantity=0,
                    reason="Squeeze ON - waiting for fire"
                )
        
        # Momentum direction must be bullish
        if indicators.squeeze_direction == 1:  # Bullish
            score += 0.2
            reasons.append(f"Momentum bullish ({indicators.squeeze_momentum:.2f})")
        elif indicators.squeeze_direction == -1:  # Bearish
            return TradeSignal(
                agent_type=self.agent_type,
                action="HOLD",
                side=OrderAction.BUY,
                quantity=0,
                reason=f"Momentum bearish ({indicators.squeeze_momentum:.2f})"
            )
        
        # Momentum should be rising (bars getting taller)
        if indicators.squeeze_momentum_rising:
            score += 0.15
            reasons.append("Momentum rising")
        
        # =================================================================
        # SECONDARY CONFIRMATIONS (Optional boosters)
        # =================================================================
        
        # RSI not overbought
        if indicators.rsi < self.config.RSI_OVERBOUGHT:
            if indicators.rsi > 40:
                score += 0.05
                reasons.append(f"RSI OK ({indicators.rsi:.1f})")
        else:
            # RSI overbought - reduce score but don't block
            score -= 0.1
            reasons.append(f"RSI high ({indicators.rsi:.1f})")
        
        # Price above VWAP (optional confirmation)
        if current_price > indicators.vwap:
            score += 0.05
            reasons.append("Above VWAP")
        
        # ADX trending (optional confirmation)
        if indicators.adx > 20 and indicators.plus_di > indicators.minus_di:
            score += 0.05
            reasons.append(f"ADX confirms ({indicators.adx:.1f})")
        
        # =================================================================
        # DECISION
        # =================================================================
        # Require minimum score of 0.5 for entry
        if score >= 0.5:
            atr = indicators.atr if indicators.atr > 0 else ticks_to_points(self.config.STOP_LOSS_TICKS)
            
            stop_loss = round(ask_price - (atr * 2), 2)
            take_profit = round(ask_price + (atr * 3), 2)
            
            return TradeSignal(
                agent_type=self.agent_type,
                action="ENTER",
                side=OrderAction.BUY,
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
            side=OrderAction.BUY,
            quantity=0,
            reason=f"Score {score:.2f}: " + ", ".join(reasons) if reasons else "No signals",
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
                side=OrderAction.SELL,
                quantity=0,
                reason="No position"
            )
        
        entry_price = self.current_position.average_price
        pnl = current_price - entry_price
        pnl_ticks = pnl * 4
        
        reasons = []
        should_exit = False
        
        # 1. Stop Loss
        if pnl_ticks <= -self.config.STOP_LOSS_TICKS:
            should_exit = True
            reasons.append(f"Stop loss hit ({pnl_ticks:.0f} ticks)")
        
        # 2. Take Profit
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
        
        # 6. ADX Trend Reversal
        if indicators.plus_di < indicators.minus_di and pnl_ticks > 0:
            should_exit = True
            reasons.append("ADX trend reversal")
        
        if should_exit:
            return TradeSignal(
                agent_type=self.agent_type,
                action="EXIT",
                side=OrderAction.SELL,
                quantity=abs(self.current_position.quantity),
                reason=" | ".join(reasons)
            )
        
        return TradeSignal(
            agent_type=self.agent_type,
            action="HOLD",
            side=OrderAction.SELL,
            quantity=0,
            reason=f"Holding position (PnL: {pnl_ticks:.0f} ticks)"
        )
    
    def _update_position(self):
        """Update current position from broker"""
        position = self.client.get_es_position()
        
        if position and position.side == "Long":
            self.current_position = position
        else:
            self.current_position = None
    
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
                trades = self.client.place_bracket_order(
                    action=signal.side,
                    quantity=signal.quantity,
                    entry_price=None,  # Market order
                    stop_loss_price=signal.stop_loss,
                    take_profit_price=signal.take_profit,
                    entry_type="MKT"
                )
                
                if trades:
                    self.daily_trades += 1
                    self.active_orders = trades
                    self.logger.info(
                        f"LONG ENTRY: {signal.quantity} @ MKT | "
                        f"SL: {signal.stop_loss:.2f} | TP: {signal.take_profit:.2f} | "
                        f"Reason: {signal.reason}"
                    )
                    return True
                    
            elif signal.action == "EXIT":
                # Cancel existing orders and flatten
                result = self.client.flatten_position()
                
                if result:
                    self.active_orders = []
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
            bars = self.client.get_bars(bar_count=100)
            quote = self.client.get_quote()
            
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
                "macd": self.last_indicators.macd_histogram if self.last_indicators else 0,
                "squeeze_on": self.last_indicators.squeeze_on if self.last_indicators else False,
                "squeeze_fired": self.last_indicators.squeeze_fired if self.last_indicators else False,
                "squeeze_momentum": self.last_indicators.squeeze_momentum if self.last_indicators else 0,
                "squeeze_direction": self.last_indicators.squeeze_direction if self.last_indicators else 0
            }
        }
