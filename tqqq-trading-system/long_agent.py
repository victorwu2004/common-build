# TQQQ Long Agent - 2-Level Position Sizing
# Level 1: 1000 shares | Level 2: 2000 shares

from typing import Optional, Dict, Any, List

from config import (
    TradingConfig, AgentType, OrderSide, PositionLevel,
    Position, TradeSignal, setup_logging, is_market_open,
    get_shares, get_stop_pct, get_target_pct,
    calc_stop, calc_target, calc_pnl_pct, calc_pnl_dollars
)
from tradestation_client import TradeStationClient
from indicators import TechnicalIndicators, Indicators


class LongAgent:
    """
    TQQQ Long Agent with 2-Level Position Sizing
    
    Level 1 (1000 shares): Score >= 0.50
    Level 2 (2000 shares): Score >= 0.70 + squeeze fired + momentum rising + ADX > 25
    """
    
    def __init__(self, config: TradingConfig, client: TradeStationClient):
        self.config = config
        self.client = client
        self.logger = setup_logging("Long")
        
        self.position: Optional[Position] = None
        self.level: PositionLevel = PositionLevel.NONE
        self.indicators: Optional[Indicators] = None
        self.last_price: float = 0.0
        
        self.daily_pnl: float = 0.0
        self.daily_trades: int = 0
        self.l1_trades: int = 0
        self.l2_trades: int = 0
    
    def analyze(self, bars: List[Dict], quote: Dict) -> TradeSignal:
        """Analyze market and generate signal with position level"""
        
        self.indicators = TechnicalIndicators.calculate_all(bars, self.config)
        self.last_price = float(quote.get("Last", 0))
        ask = float(quote.get("Ask", self.last_price))
        
        self._update_position()
        
        if self.position and self.position.quantity > 0:
            return self._check_exit()
        else:
            return self._check_entry(ask)
    
    def _check_entry(self, ask: float) -> TradeSignal:
        """Check for long entry with level determination"""
        
        ind = self.indicators
        reasons = []
        score = 0.0
        
        # =====================================================================
        # REQUIRED: EMA Bullish
        # =====================================================================
        if ind.ema_fast > ind.ema_slow:
            score += 0.25
            reasons.append(f"EMA {self.config.EMA_FAST}>{self.config.EMA_SLOW}")
        else:
            return self._hold(f"EMA bearish ({ind.ema_fast:.2f} < {ind.ema_slow:.2f})")
        
        # =====================================================================
        # TTM SQUEEZE
        # =====================================================================
        if ind.squeeze_fired:
            score += 0.25
            reasons.append("Squeeze FIRED")
        elif not ind.squeeze_on:
            score += 0.10
            reasons.append("Squeeze off")
        else:
            return self._hold("Squeeze ON - waiting")
        
        # Momentum positive
        if ind.momentum_direction == 1:
            score += 0.20
            reasons.append(f"Mom+ ({ind.squeeze_momentum:.2f})")
        elif ind.momentum_direction == -1:
            return self._hold(f"Momentum bearish ({ind.squeeze_momentum:.2f})")
        
        # Momentum rising
        if ind.momentum_rising:
            score += 0.10
            reasons.append("Mom rising")
        
        # =====================================================================
        # SECONDARY
        # =====================================================================
        if ind.rsi < self.config.RSI_OVERBOUGHT and ind.rsi > 40:
            score += 0.05
            reasons.append(f"RSI {ind.rsi:.0f}")
        
        if self.last_price > ind.vwap:
            score += 0.05
            reasons.append(">VWAP")
        
        if ind.adx > 20 and ind.plus_di > ind.minus_di:
            score += 0.05
            reasons.append(f"ADX {ind.adx:.0f}")
        
        # =====================================================================
        # DETERMINE LEVEL
        # =====================================================================
        level = self._determine_level(score, ind)
        
        if level == PositionLevel.NONE:
            return self._hold(f"Score {score:.2f} < {self.config.LEVEL_1_MIN_SCORE}")
        
        shares = get_shares(level, self.config)
        stop = calc_stop(ask, level, self.config, is_long=True)
        target = calc_target(ask, level, self.config, is_long=True)
        
        # Check max position value
        value = ask * shares
        if value > self.config.MAX_POSITION_VALUE:
            return self._hold(f"Value ${value:,.0f} > max ${self.config.MAX_POSITION_VALUE:,.0f}")
        
        level_tag = f"L{level.value}"
        return TradeSignal(
            agent_type=AgentType.LONG,
            action="ENTER",
            side=OrderSide.BUY,
            quantity=shares,
            level=level,
            price=ask,
            stop_loss=stop,
            take_profit=target,
            reason=f"[{level_tag}] " + " | ".join(reasons),
            score=score
        )
    
    def _determine_level(self, score: float, ind: Indicators) -> PositionLevel:
        """Determine position level based on score and conditions"""
        
        # Check Level 2 first
        if score >= self.config.LEVEL_2_MIN_SCORE:
            l2_ok = True
            
            if self.config.LEVEL_2_REQUIRES_SQUEEZE_FIRE and not ind.squeeze_fired:
                l2_ok = False
            
            if self.config.LEVEL_2_REQUIRES_MOMENTUM_RISING and not ind.momentum_rising:
                l2_ok = False
            
            if ind.adx < self.config.LEVEL_2_MIN_ADX:
                l2_ok = False
            
            if l2_ok:
                return PositionLevel.LEVEL_2
        
        # Check Level 1
        if score >= self.config.LEVEL_1_MIN_SCORE:
            return PositionLevel.LEVEL_1
        
        return PositionLevel.NONE
    
    def _check_exit(self) -> TradeSignal:
        """Check for exit signals"""
        
        ind = self.indicators
        entry = self.position.average_price
        shares = self.position.quantity
        
        pnl_pct = calc_pnl_pct(entry, self.last_price, is_long=True)
        pnl_dlr = calc_pnl_dollars(entry, self.last_price, shares, is_long=True)
        
        stop_pct = get_stop_pct(self.level, self.config)
        target_pct = get_target_pct(self.level, self.config)
        
        reasons = []
        
        # Stop loss
        if pnl_pct <= -stop_pct:
            reasons.append(f"Stop hit ({pnl_pct:.2f}%)")
        
        # Take profit
        if pnl_pct >= target_pct:
            reasons.append(f"Target hit ({pnl_pct:.2f}%)")
        
        # EMA crossover
        if ind.ema_fast < ind.ema_slow:
            reasons.append("EMA bearish")
        
        # RSI extreme
        if ind.rsi > 80:
            reasons.append(f"RSI {ind.rsi:.0f}")
        
        # Momentum reversal with profit
        if ind.momentum_direction == -1 and pnl_pct > 0.5:
            reasons.append("Mom reversal + profit")
        
        if reasons:
            return TradeSignal(
                agent_type=AgentType.LONG,
                action="EXIT",
                side=OrderSide.SELL,
                quantity=shares,
                level=self.level,
                reason=f"[L{self.level.value}] " + " | ".join(reasons)
            )
        
        return TradeSignal(
            agent_type=AgentType.LONG,
            action="HOLD",
            side=OrderSide.SELL,
            quantity=0,
            level=self.level,
            reason=f"[L{self.level.value}] Holding: {pnl_pct:+.2f}% (${pnl_dlr:+,.0f})"
        )
    
    def _hold(self, reason: str) -> TradeSignal:
        return TradeSignal(
            agent_type=AgentType.LONG,
            action="HOLD",
            side=OrderSide.BUY,
            quantity=0,
            level=PositionLevel.NONE,
            reason=reason
        )
    
    def _update_position(self):
        """Update position from broker"""
        self.position = None
        self.level = PositionLevel.NONE
        
        for pos in self.client.get_positions():
            if pos.symbol == self.config.SYMBOL and pos.side == "Long":
                self.position = pos
                # Determine level by quantity
                if pos.quantity >= self.config.LEVEL_2_SHARES:
                    self.level = PositionLevel.LEVEL_2
                elif pos.quantity >= self.config.LEVEL_1_SHARES:
                    self.level = PositionLevel.LEVEL_1
                break
    
    def execute(self, signal: TradeSignal) -> bool:
        """Execute trading signal"""
        
        if signal.action == "HOLD":
            return True
        
        if self.daily_trades >= self.config.MAX_DAILY_TRADES:
            self.logger.warning("Max daily trades reached")
            return False
        
        if self.daily_pnl <= -self.config.MAX_DAILY_LOSS:
            self.logger.warning("Max daily loss reached")
            return False
        
        try:
            if signal.action == "ENTER":
                result = self.client.place_bracket_order(
                    quantity=signal.quantity,
                    side=signal.side.value,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit
                )
                
                if result:
                    self.daily_trades += 1
                    self.level = signal.level
                    
                    if signal.level == PositionLevel.LEVEL_2:
                        self.l2_trades += 1
                    else:
                        self.l1_trades += 1
                    
                    value = signal.price * signal.quantity
                    stop_pct = get_stop_pct(signal.level, self.config)
                    target_pct = get_target_pct(signal.level, self.config)
                    
                    self.logger.info(
                        f"🟢 LONG [L{signal.level.value}]: {signal.quantity} shares @ ${signal.price:.2f} "
                        f"(${value:,.0f}) | SL: ${signal.stop_loss:.2f} (-{stop_pct}%) | "
                        f"TP: ${signal.take_profit:.2f} (+{target_pct}%)"
                    )
                    return True
            
            elif signal.action == "EXIT":
                self.client.cancel_all_orders()
                if self.client.flatten_position():
                    self.logger.info(f"🔴 EXIT [L{signal.level.value}]: {signal.reason}")
                    self.level = PositionLevel.NONE
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Execute error: {e}")
            return False
    
    def run_cycle(self) -> Optional[TradeSignal]:
        """Run one analysis cycle"""
        
        if not is_market_open(self.config):
            return None
        
        bars = self.client.get_bars()
        quote = self.client.get_quote()
        
        if not bars or not quote:
            return None
        
        signal = self.analyze(bars, quote)
        
        if signal.action != "HOLD":
            self.execute(signal)
        
        return signal
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "position": self.position.quantity if self.position else 0,
            "level": self.level.value,
            "daily_pnl": self.daily_pnl,
            "trades": self.daily_trades,
            "l1_trades": self.l1_trades,
            "l2_trades": self.l2_trades,
            "price": self.last_price
        }
