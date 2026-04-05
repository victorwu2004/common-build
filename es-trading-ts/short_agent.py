# Short Agent for TradeStation
# EMA Crossover + TTM Squeeze Strategy - Short Positions Only

from typing import Optional, Dict, Any, List
from datetime import datetime
import threading

from config import (
    TradingConfig, AgentType, OrderSide, OrderType,
    TradeSignal, Position, setup_logging, is_trading_hours,
    ticks_to_points, calculate_dollar_value
)
from tradestation_client import TradeStationClient
from indicators import TechnicalIndicators, IndicatorValues


class ShortAgent:
    """
    Trading agent that focuses on SHORT positions only.
    Uses EMA Crossover + TTM Squeeze strategy.
    
    Entry conditions:
    1. EMA 8 < EMA 21 (bearish trend) - REQUIRED
    2. TTM Squeeze has fired (was ON, now OFF) - REQUIRED if configured
    3. Squeeze momentum is negative (bearish) - REQUIRED
    4. Momentum is rising in magnitude (bars getting taller downward) - bonus
    
    Exit conditions:
    - Stop loss hit (bracket order)
    - Take profit hit (bracket order)
    - EMA crossover bullish
    - RSI < 20 (extremely oversold)
    """
    
    def __init__(self, config: TradingConfig, client: TradeStationClient):
        self.config = config
        self.client = client
        self.logger = setup_logging("ShortAgent")
        
        self.agent_type = AgentType.SHORT
        self.is_running = False
        self.current_position: Optional[Position] = None
        self.active_orders: List[Dict[str, Any]] = []
        
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
            side=OrderSide.SELL_SHORT,
            quantity=0,
            reason="No clear signal"
        )
        
        # Check if we have a position
        self._update_position()
        
        if self.current_position and self.current_position.quantity > 0:
            # We have a short position - look for exit signals
            signal = self._check_exit_signals(indicators, current_price)
        else:
            # No position - look for entry signals
            signal = self._check_entry_signals(indicators, current_price, bid)
        
        self.last_signal = signal
        return signal
    
    def _check_entry_signals(
        self, 
        indicators: IndicatorValues, 
        current_price: float,
        bid_price: float
    ) -> TradeSignal:
        """
        Check for bearish entry signals using EMA Crossover + TTM Squeeze strategy.
        
        Entry conditions:
        1. EMA 8 < EMA 21 (bearish trend)
        2. TTM Squeeze has fired (squeeze off) OR momentum is bearish
        3. Squeeze momentum is negative (bearish)
        4. Momentum is rising in magnitude (getting more negative)
        """
        
        reasons = []
        score = 0.0
        
        # =================================================================
        # PRIMARY FILTER: EMA Crossover (REQUIRED)
        # =================================================================
        if indicators.ema_fast < indicators.ema_slow:
            score += 0.25
            reasons.append(f"EMA{self.config.EMA_FAST}x{self.config.EMA_SLOW} bearish")
        else:
            return TradeSignal(
                agent_type=self.agent_type,
                action="HOLD",
                side=OrderSide.SELL_SHORT,
                quantity=0,
                reason=f"EMA bullish ({indicators.ema_fast:.2f} > {indicators.ema_slow:.2f})"
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
                    side=OrderSide.SELL_SHORT,
                    quantity=0,
                    reason="Squeeze ON - waiting for fire"
                )
        
        # Momentum direction must be bearish
        if indicators.squeeze_direction == -1:  # Bearish
            score += 0.2
            reasons.append(f"Momentum bearish ({indicators.squeeze_momentum:.2f})")
        elif indicators.squeeze_direction == 1:  # Bullish
            return TradeSignal(
                agent_type=self.agent_type,
                action="HOLD",
                side=OrderSide.SELL_SHORT,
                quantity=0,
                reason=f"Momentum bullish ({indicators.squeeze_momentum:.2f})"
            )
        
        # Momentum should be rising in magnitude (bars getting taller downward)
        if indicators.squeeze_momentum_rising:
            score += 0.15
            reasons.append("Momentum rising")
        
        # =================================================================
        # SECONDARY CONFIRMATIONS (Optional boosters)
        # =================================================================
        
        # RSI not oversold
        if indicators.rsi > self.config.RSI_OVERSOLD:
            if indicators.rsi < 60:
                score += 0.05
                reasons.append(f"RSI OK ({indicators.rsi:.1f})")
        else:
            # RSI oversold - reduce score but don't block
            score -= 0.1
            reasons.append(f"RSI low ({indicators.rsi:.1f})")
        
        # Price below VWAP (optional confirmation)
        if current_price < indicators.vwap:
            score += 0.05
            reasons.append("Below VWAP")
        
        # ADX trending (optional confirmation)
        if indicators.adx > 20 and indicators.minus_di > indicators.plus_di:
            score += 0.05
            reasons.append(f"ADX confirms ({indicators.adx:.1f})")
        
        # =================================================================
        # DECISION
        # =================================================================
        # Require minimum score of 0.5 for entry
        if score >= 0.5:
            atr = indicators.atr if indicators.atr > 0 else ticks_to_points(self.config.STOP_LOSS_TICKS)
            
            stop_loss = round(bid_price + (atr * 2), 2)
            take_profit = round(bid_price - (atr * 3), 2)
            
            return TradeSignal(
                agent_type=self.agent_type,
                action="ENTER",
                side=OrderSide.SELL_SHORT,
                quantity=self.config.DEFAULT_CONTRACTS,
                price=bid_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason=" | ".join(reasons),
                confidence=score
            )
        
        return TradeSignal(
            agent_type=self.agent_type,
            action="HOLD",
            side=OrderSide.SELL_SHORT,
            quantity=0,
            reason=f"Score {score:.2f}: " + ", ".join(reasons) if reasons else "No signals",
            confidence=score
        )
    
    def _check_exit_signals(
        self,
        indicators: IndicatorValues,
        current_price: float
    ) -> TradeSignal:
        """Check for exit signals when holding a short position"""
        
        if not self.current_position:
            return TradeSignal(
                agent_type=self.agent_type,
                action="HOLD",
                side=OrderSide.BUY_TO_COVER,
                quantity=0,
                reason="No position"
            )
        
        entry_price = self.current_position.average_price
        # For shorts: profit when price goes down
        pnl = entry_price - current_price
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
        
        # 3. EMA Bullish Crossover
        if indicators.ema_fast > indicators.ema_slow:
            should_exit = True
            reasons.append("EMA bullish crossover")
        
        # 4. RSI Extremely Oversold
        if indicators.rsi < 20:
            should_exit = True
            reasons.append(f"RSI extremely oversold ({indicators.rsi:.1f})")
        
        # 5. Squeeze momentum turned bullish with profit
        if indicators.squeeze_direction == 1 and pnl_ticks > 8:
            should_exit = True
            reasons.append("Momentum turned bullish + profit")
        
        # 6. ADX Trend Reversal
        if indicators.plus_di > indicators.minus_di and pnl_ticks > 0:
            should_exit = True
            reasons.append("ADX trend reversal")
        
        if should_exit:
            return TradeSignal(
                agent_type=self.agent_type,
                action="EXIT",
                side=OrderSide.BUY_TO_COVER,
                quantity=abs(self.current_position.quantity),
                reason=" | ".join(reasons)
            )
        
        return TradeSignal(
            agent_type=self.agent_type,
            action="HOLD",
            side=OrderSide.BUY_TO_COVER,
            quantity=0,
            reason=f"Holding position (PnL: {pnl_ticks:.0f} ticks)"
        )
    
    def _update_position(self):
        """Update current position from broker"""
        positions = self.client.get_positions()
        
        self.current_position = None
        for pos in positions:
            if pos.symbol == self.config.SYMBOL and pos.side == "Short":
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
                        f"SHORT ENTRY: {signal.quantity} @ {signal.price:.2f} | "
                        f"SL: {signal.stop_loss:.2f} | TP: {signal.take_profit:.2f} | "
                        f"Reason: {signal.reason}"
                    )
                    return True
                    
            elif signal.action == "EXIT":
                # Cancel existing orders and flatten
                self.client.cancel_all_orders()
                result = self.client.flatten_position()
                
                if result:
                    self.logger.info(f"SHORT EXIT: {signal.reason}")
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
            bars = self.client.get_bars()
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
        self.logger.info("Short Agent started")
    
    def stop(self):
        """Stop the agent"""
        self.is_running = False
        self.logger.info("Short Agent stopped")
    
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
                "squeeze_on": self.last_indicators.squeeze_on if self.last_indicators else False,
                "squeeze_fired": self.last_indicators.squeeze_fired if self.last_indicators else False,
                "squeeze_momentum": self.last_indicators.squeeze_momentum if self.last_indicators else 0,
                "squeeze_direction": self.last_indicators.squeeze_direction if self.last_indicators else 0
            }
        }
