# ES Dual Agent Trading System - Main Orchestrator
# Coordinates Long and Short agents

import time
import threading
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json

from config import TradingConfig, setup_logging, is_trading_hours
from tradestation_client import TradeStationClient
from long_agent import LongAgent
from short_agent import ShortAgent


class TradingOrchestrator:
    """
    Main orchestrator for the dual-agent trading system.
    
    Coordinates:
    - Long Agent: Trades bullish setups
    - Short Agent: Trades bearish setups
    
    Features:
    - Agent coordination (prevents conflicting positions)
    - Risk management across both agents
    - Daily PnL tracking
    - Graceful shutdown
    """
    
    def __init__(self, config: Optional[TradingConfig] = None):
        self.config = config or TradingConfig()
        self.logger = setup_logging("Orchestrator")
        
        # Initialize client
        self.client = TradeStationClient(self.config)
        
        # Initialize agents
        self.long_agent = LongAgent(self.config, self.client)
        self.short_agent = ShortAgent(self.config, self.client)
        
        # State
        self.is_running = False
        self.cycle_count = 0
        self.start_time: Optional[datetime] = None
        
        # Coordination
        self._lock = threading.Lock()
        self._allow_simultaneous = False  # If True, both agents can have positions
        
        # Performance
        self.total_pnl = 0.0
        self.daily_pnl = 0.0
        self.last_daily_reset = datetime.now().date()
        
        # Shutdown handling
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info("Shutdown signal received")
        self.stop()
        sys.exit(0)
    
    def initialize(self) -> bool:
        """Initialize the trading system"""
        self.logger.info("=" * 60)
        self.logger.info("ES Dual Agent Trading System")
        self.logger.info("=" * 60)
        
        # Authenticate
        if not self.client.authenticate():
            self.logger.error("Failed to authenticate with TradeStation")
            return False
        
        # Get account info
        accounts = self.client.get_accounts()
        if not accounts:
            self.logger.error("Failed to get accounts")
            return False
        
        self.logger.info(f"Connected to account: {self.config.ACCOUNT_ID}")
        
        # Get balances
        balances = self.client.get_balances()
        if balances:
            self.logger.info(f"Account Balance: ${balances.get('CashBalance', 0):,.2f}")
            self.logger.info(f"Buying Power: ${balances.get('BuyingPower', 0):,.2f}")
        
        # Check existing positions
        positions = self.client.get_positions()
        if positions:
            self.logger.info(f"Existing positions: {len(positions)}")
            for pos in positions:
                self.logger.info(f"  {pos.symbol}: {pos.quantity} @ {pos.average_price}")
        
        # Get current quote
        quote = self.client.get_quote(self.config.SYMBOL)
        if quote:
            self.logger.info(f"Current {self.config.SYMBOL} price: {quote.get('Last')}")
        
        self.logger.info("-" * 60)
        self.logger.info(f"Symbol: {self.config.SYMBOL}")
        self.logger.info(f"Max Contracts Long: {self.config.MAX_CONTRACTS_LONG}")
        self.logger.info(f"Max Contracts Short: {self.config.MAX_CONTRACTS_SHORT}")
        self.logger.info(f"Stop Loss: {self.config.STOP_LOSS_TICKS} ticks (${self.config.STOP_LOSS_TICKS * 12.50:.2f})")
        self.logger.info(f"Take Profit: {self.config.TAKE_PROFIT_TICKS} ticks (${self.config.TAKE_PROFIT_TICKS * 12.50:.2f})")
        self.logger.info(f"Max Daily Loss: ${self.config.MAX_DAILY_LOSS:.2f}")
        self.logger.info(f"Max Daily Trades: {self.config.MAX_DAILY_TRADES}")
        self.logger.info("=" * 60)
        
        return True
    
    def _check_daily_reset(self):
        """Reset daily counters if new day"""
        today = datetime.now().date()
        if today > self.last_daily_reset:
            self.logger.info("New trading day - resetting daily counters")
            self.daily_pnl = 0.0
            self.long_agent.daily_pnl = 0.0
            self.long_agent.daily_trades = 0
            self.short_agent.daily_pnl = 0.0
            self.short_agent.daily_trades = 0
            self.last_daily_reset = today
    
    def _can_agent_trade(self, agent_type: str) -> bool:
        """Check if an agent is allowed to trade"""
        
        with self._lock:
            # Check daily limits
            total_daily_pnl = self.long_agent.daily_pnl + self.short_agent.daily_pnl
            if total_daily_pnl <= -self.config.MAX_DAILY_LOSS:
                self.logger.warning("Daily loss limit reached - no new trades")
                return False
            
            total_daily_trades = self.long_agent.daily_trades + self.short_agent.daily_trades
            if total_daily_trades >= self.config.MAX_DAILY_TRADES * 2:
                self.logger.warning("Daily trade limit reached")
                return False
            
            # If not allowing simultaneous positions
            if not self._allow_simultaneous:
                # Check if other agent has a position
                if agent_type == "LONG" and self.short_agent.current_position:
                    if self.short_agent.current_position.quantity > 0:
                        return False
                elif agent_type == "SHORT" and self.long_agent.current_position:
                    if self.long_agent.current_position.quantity > 0:
                        return False
            
            return True
    
    def _run_agents(self):
        """Run one cycle for both agents"""
        
        self._check_daily_reset()
        
        # Run Long Agent
        if self._can_agent_trade("LONG"):
            long_signal = self.long_agent.run_cycle()
            if long_signal and long_signal.action != "HOLD":
                self.logger.info(f"[LONG] {long_signal.action}: {long_signal.reason}")
        
        # Small delay between agents
        time.sleep(0.5)
        
        # Run Short Agent
        if self._can_agent_trade("SHORT"):
            short_signal = self.short_agent.run_cycle()
            if short_signal and short_signal.action != "HOLD":
                self.logger.info(f"[SHORT] {short_signal.action}: {short_signal.reason}")
        
        self.cycle_count += 1
    
    def _print_status(self):
        """Print current status"""
        long_status = self.long_agent.get_status()
        short_status = self.short_agent.get_status()
        
        self.logger.info("-" * 40)
        self.logger.info(f"Cycle: {self.cycle_count} | Price: {long_status['last_price']:.2f}")
        self.logger.info(
            f"LONG: {long_status['last_signal']['action']} | "
            f"Pos: {long_status['current_position']['quantity']} | "
            f"PnL: ${long_status['current_position']['unrealized_pnl']:.2f}"
        )
        self.logger.info(
            f"SHORT: {short_status['last_signal']['action']} | "
            f"Pos: {short_status['current_position']['quantity']} | "
            f"PnL: ${short_status['current_position']['unrealized_pnl']:.2f}"
        )
        self.logger.info(
            f"Daily Trades: {long_status['daily_trades'] + short_status['daily_trades']} | "
            f"Daily PnL: ${long_status['daily_pnl'] + short_status['daily_pnl']:.2f}"
        )
    
    def start(self):
        """Start the trading system"""
        
        if not self.initialize():
            self.logger.error("Initialization failed")
            return
        
        self.is_running = True
        self.start_time = datetime.now()
        self.long_agent.start()
        self.short_agent.start()
        
        self.logger.info("Trading system started")
        self.logger.info("Press Ctrl+C to stop")
        
        status_interval = 10  # Print status every N cycles
        
        try:
            while self.is_running:
                # Check trading hours
                if not is_trading_hours(self.config):
                    self.logger.info("Outside trading hours - waiting...")
                    time.sleep(60)
                    continue
                
                # Run trading cycle
                self._run_agents()
                
                # Print status periodically
                if self.cycle_count % status_interval == 0:
                    self._print_status()
                
                # Wait before next cycle
                time.sleep(self.config.AGENT_SYNC_INTERVAL)
                
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the trading system"""
        self.logger.info("Stopping trading system...")
        
        self.is_running = False
        self.long_agent.stop()
        self.short_agent.stop()
        
        # Print final summary
        self._print_summary()
        
        self.logger.info("Trading system stopped")
    
    def _print_summary(self):
        """Print trading session summary"""
        
        if not self.start_time:
            return
        
        duration = datetime.now() - self.start_time
        
        long_status = self.long_agent.get_status()
        short_status = self.short_agent.get_status()
        
        total_trades = long_status['daily_trades'] + short_status['daily_trades']
        total_pnl = long_status['daily_pnl'] + short_status['daily_pnl']
        
        self.logger.info("=" * 60)
        self.logger.info("SESSION SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Duration: {duration}")
        self.logger.info(f"Total Cycles: {self.cycle_count}")
        self.logger.info(f"Total Trades: {total_trades}")
        self.logger.info(f"  Long Trades: {long_status['daily_trades']}")
        self.logger.info(f"  Short Trades: {short_status['daily_trades']}")
        self.logger.info(f"Total PnL: ${total_pnl:.2f}")
        self.logger.info(f"  Long PnL: ${long_status['daily_pnl']:.2f}")
        self.logger.info(f"  Short PnL: ${short_status['daily_pnl']:.2f}")
        self.logger.info("=" * 60)
    
    def get_status(self) -> Dict[str, Any]:
        """Get full system status"""
        return {
            "is_running": self.is_running,
            "cycle_count": self.cycle_count,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "long_agent": self.long_agent.get_status(),
            "short_agent": self.short_agent.get_status(),
            "total_daily_pnl": self.long_agent.daily_pnl + self.short_agent.daily_pnl,
            "total_daily_trades": self.long_agent.daily_trades + self.short_agent.daily_trades
        }


def main():
    """Main entry point"""
    
    # Create config (can be customized)
    config = TradingConfig()
    
    # Override with environment variables or command line args if needed
    # config.SYMBOL = "ESH25"  # March 2025 contract
    # config.MAX_CONTRACTS_LONG = 1
    # config.MAX_CONTRACTS_SHORT = 1
    
    # Create and start orchestrator
    orchestrator = TradingOrchestrator(config)
    orchestrator.start()


if __name__ == "__main__":
    main()
