# TQQQ Trading System - Main Orchestrator
# 2-Level Position Sizing: 1000 or 2000 shares

import time
import signal
import sys
from datetime import datetime

from config import TradingConfig, PositionLevel, setup_logging, is_market_open
from tradestation_client import TradeStationClient
from long_agent import LongAgent
from short_agent import ShortAgent


class TradingSystem:
    """
    TQQQ Trading System with 2-Level Position Sizing
    
    Position Levels:
    - Level 1: 1000 shares (score >= 0.50)
    - Level 2: 2000 shares (score >= 0.70 + strong confirmation)
    
    Risk Parameters:
    - L1: Stop 1.5% / Target 3.0%
    - L2: Stop 1.0% / Target 2.0% (tighter due to larger size)
    """
    
    def __init__(self):
        self.config = TradingConfig()
        self.logger = setup_logging("System")
        
        self.client = TradeStationClient(self.config)
        self.long_agent = None
        self.short_agent = None
        
        self.running = False
        self.cycle = 0
        
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)
    
    def _shutdown(self, *args):
        self.logger.info("Shutting down...")
        self.running = False
    
    def initialize(self) -> bool:
        """Initialize the trading system"""
        
        self.logger.info("=" * 60)
        self.logger.info("TQQQ TRADING SYSTEM - 2-Level Position Sizing")
        self.logger.info("=" * 60)
        
        if not self.client.authenticate():
            self.logger.error("Authentication failed")
            return False
        
        self.long_agent = LongAgent(self.config, self.client)
        self.short_agent = ShortAgent(self.config, self.client)
        
        # Display configuration
        balances = self.client.get_balances()
        quote = self.client.get_quote()
        
        if balances:
            self.logger.info(f"Account: {self.config.ACCOUNT_ID}")
            self.logger.info(f"Balance: ${balances.get('CashBalance', 0):,.2f}")
            self.logger.info(f"Buying Power: ${balances.get('BuyingPower', 0):,.2f}")
        
        if quote:
            price = float(quote.get('Last', 0))
            l1_value = price * self.config.LEVEL_1_SHARES
            l2_value = price * self.config.LEVEL_2_SHARES
            
            self.logger.info("-" * 60)
            self.logger.info(f"Symbol: {self.config.SYMBOL} @ ${price:.2f}")
            self.logger.info("-" * 60)
            self.logger.info("POSITION LEVELS:")
            self.logger.info(f"  Level 1: {self.config.LEVEL_1_SHARES} shares (${l1_value:,.0f})")
            self.logger.info(f"           Stop: {self.config.L1_STOP_LOSS_PCT}% | Target: {self.config.L1_TAKE_PROFIT_PCT}%")
            self.logger.info(f"           Requires: Score >= {self.config.LEVEL_1_MIN_SCORE}")
            self.logger.info(f"  Level 2: {self.config.LEVEL_2_SHARES} shares (${l2_value:,.0f})")
            self.logger.info(f"           Stop: {self.config.L2_STOP_LOSS_PCT}% | Target: {self.config.L2_TAKE_PROFIT_PCT}%")
            self.logger.info(f"           Requires: Score >= {self.config.LEVEL_2_MIN_SCORE} + Squeeze Fire + Mom Rising + ADX>{self.config.LEVEL_2_MIN_ADX}")
            self.logger.info("-" * 60)
            self.logger.info(f"Strategy: EMA {self.config.EMA_FAST}/{self.config.EMA_SLOW} + TTM Squeeze")
            self.logger.info(f"Max Daily Loss: ${self.config.MAX_DAILY_LOSS:,.0f}")
            self.logger.info(f"Max Trades/Day: {self.config.MAX_DAILY_TRADES}")
        
        self.logger.info("=" * 60)
        return True
    
    def run(self):
        """Main trading loop"""
        
        if not self.initialize():
            return
        
        self.running = True
        self.logger.info("System started - Press Ctrl+C to stop")
        
        try:
            while self.running:
                if not is_market_open(self.config):
                    self.logger.info("Market closed - waiting...")
                    time.sleep(60)
                    continue
                
                self._run_cycle()
                time.sleep(self.config.CYCLE_INTERVAL)
                
        except KeyboardInterrupt:
            pass
        finally:
            self._print_summary()
    
    def _run_cycle(self):
        """Run one trading cycle"""
        
        self.cycle += 1
        
        # Run Long Agent
        long_signal = self.long_agent.run_cycle()
        
        # Run Short Agent (only if no long position)
        short_signal = None
        if not (self.long_agent.position and self.long_agent.position.quantity > 0):
            short_signal = self.short_agent.run_cycle()
        
        # Log status every 10 cycles
        if self.cycle % 10 == 0:
            self._print_status(long_signal, short_signal)
    
    def _print_status(self, long_signal, short_signal):
        """Print current status"""
        
        ind = self.long_agent.indicators
        price = self.long_agent.last_price
        
        squeeze = "ON 🔴" if ind.squeeze_on else "OFF 🟢"
        if ind.squeeze_fired:
            squeeze = "FIRED ⚡"
        
        mom_dir = "↑" if ind.momentum_direction > 0 else "↓" if ind.momentum_direction < 0 else "→"
        
        self.logger.info("-" * 50)
        self.logger.info(f"Cycle {self.cycle} | TQQQ ${price:.2f}")
        self.logger.info(f"EMA: {ind.ema_fast:.2f}/{ind.ema_slow:.2f} | Squeeze: {squeeze} | Mom: {ind.squeeze_momentum:.2f} {mom_dir}")
        
        # Long status
        long_status = self.long_agent.get_status()
        if long_status['position'] > 0:
            self.logger.info(f"LONG [L{long_status['level']}]: {long_status['position']} shares")
        else:
            reason = long_signal.reason if long_signal else "N/A"
            self.logger.info(f"LONG: {reason[:50]}")
        
        # Short status
        short_status = self.short_agent.get_status()
        if short_status['position'] > 0:
            self.logger.info(f"SHORT [L{short_status['level']}]: {short_status['position']} shares")
        else:
            reason = short_signal.reason if short_signal else "N/A"
            self.logger.info(f"SHORT: {reason[:50]}")
    
    def _print_summary(self):
        """Print session summary"""
        
        long_s = self.long_agent.get_status()
        short_s = self.short_agent.get_status()
        
        total_trades = long_s['trades'] + short_s['trades']
        total_l1 = long_s['l1_trades'] + short_s['l1_trades']
        total_l2 = long_s['l2_trades'] + short_s['l2_trades']
        total_pnl = long_s['daily_pnl'] + short_s['daily_pnl']
        
        self.logger.info("=" * 60)
        self.logger.info("SESSION SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Total Cycles: {self.cycle}")
        self.logger.info(f"Total Trades: {total_trades}")
        self.logger.info(f"  Level 1 (1000 shares): {total_l1}")
        self.logger.info(f"  Level 2 (2000 shares): {total_l2}")
        self.logger.info(f"Daily P&L: ${total_pnl:,.2f}")
        self.logger.info("=" * 60)


def main():
    system = TradingSystem()
    system.run()


if __name__ == "__main__":
    main()
