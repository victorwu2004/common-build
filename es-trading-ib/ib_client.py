# Interactive Brokers Client
# Handles connection and API calls using ib_insync

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import threading
import time

from ib_insync import (
    IB, Contract, Future, Order, Trade, Position as IBPosition,
    MarketOrder, LimitOrder, StopOrder, BracketOrder,
    util, BarData
)

from config import (
    TradingConfig, OrderType, OrderAction,
    Position, setup_logging
)


class IBClient:
    """Interactive Brokers API Client using ib_insync"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = setup_logging("IBClient")
        
        self.ib = IB()
        self.connected = False
        self.account_id: Optional[str] = None
        
        # ES contract
        self.es_contract: Optional[Future] = None
        
        # Callbacks
        self._on_position_change: Optional[Callable] = None
        self._on_order_status: Optional[Callable] = None
        
        self._lock = threading.Lock()
    
    # ========================================================================
    # CONNECTION
    # ========================================================================
    
    def connect(self) -> bool:
        """Connect to Interactive Brokers TWS/Gateway"""
        try:
            self.logger.info(
                f"Connecting to IB at {self.config.IB_HOST}:{self.config.IB_PORT} "
                f"(clientId={self.config.IB_CLIENT_ID})"
            )
            
            self.ib.connect(
                host=self.config.IB_HOST,
                port=self.config.IB_PORT,
                clientId=self.config.IB_CLIENT_ID,
                readonly=False
            )
            
            self.connected = True
            
            # Get account
            accounts = self.ib.managedAccounts()
            if accounts:
                self.account_id = self.config.ACCOUNT_ID or accounts[0]
                self.logger.info(f"Connected to account: {self.account_id}")
            
            # Create ES contract
            self.es_contract = self._create_es_contract()
            
            # Qualify the contract
            if self.es_contract:
                qualified = self.ib.qualifyContracts(self.es_contract)
                if qualified:
                    self.es_contract = qualified[0]
                    self.logger.info(f"ES contract qualified: {self.es_contract.localSymbol}")
                else:
                    self.logger.error("Failed to qualify ES contract")
                    return False
            
            # Set up event handlers
            self.ib.positionEvent += self._on_position_event
            self.ib.orderStatusEvent += self._on_order_status_event
            self.ib.errorEvent += self._on_error_event
            
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from IB"""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            self.logger.info("Disconnected from IB")
    
    def is_connected(self) -> bool:
        """Check if connected to IB"""
        return self.ib.isConnected()
    
    def _create_es_contract(self) -> Future:
        """Create ES futures contract"""
        contract = Future(
            symbol=self.config.SYMBOL,
            lastTradeDateOrContractMonth=self.config.CONTRACT_MONTH,
            exchange=self.config.EXCHANGE,
            currency=self.config.CURRENCY
        )
        return contract
    
    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================
    
    def _on_position_event(self, position: IBPosition):
        """Handle position change events"""
        self.logger.debug(f"Position event: {position}")
        if self._on_position_change:
            self._on_position_change(position)
    
    def _on_order_status_event(self, trade: Trade):
        """Handle order status events"""
        self.logger.info(
            f"Order status: {trade.order.orderId} - {trade.orderStatus.status}"
        )
        if self._on_order_status:
            self._on_order_status(trade)
    
    def _on_error_event(self, reqId: int, errorCode: int, errorString: str, contract: Contract):
        """Handle error events"""
        # Filter out non-critical errors
        if errorCode in [2104, 2106, 2158]:  # Market data farm connected/disconnected
            return
        self.logger.error(f"IB Error {errorCode}: {errorString}")
    
    # ========================================================================
    # MARKET DATA
    # ========================================================================
    
    def get_quote(self) -> Optional[Dict[str, Any]]:
        """Get current quote for ES"""
        try:
            if not self.es_contract:
                return None
            
            # Request market data
            ticker = self.ib.reqMktData(self.es_contract, '', False, False)
            self.ib.sleep(1)  # Wait for data
            
            if ticker.last and ticker.last > 0:
                quote = {
                    "Last": ticker.last,
                    "Bid": ticker.bid,
                    "Ask": ticker.ask,
                    "BidSize": ticker.bidSize,
                    "AskSize": ticker.askSize,
                    "Volume": ticker.volume,
                    "High": ticker.high,
                    "Low": ticker.low,
                    "Close": ticker.close
                }
                
                # Cancel market data subscription
                self.ib.cancelMktData(self.es_contract)
                
                return quote
            
            self.ib.cancelMktData(self.es_contract)
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting quote: {e}")
            return None
    
    def get_bars(self, bar_count: int = 100) -> Optional[List[Dict[str, Any]]]:
        """Get historical bars for ES"""
        try:
            if not self.es_contract:
                return None
            
            # Request historical data
            bars = self.ib.reqHistoricalData(
                contract=self.es_contract,
                endDateTime='',
                durationStr=self.config.BAR_DURATION,
                barSizeSetting=self.config.BAR_SIZE,
                whatToShow='TRADES',
                useRTH=self.config.USE_RTH_ONLY,
                formatDate=1
            )
            
            if not bars:
                return None
            
            # Convert to dict format
            result = []
            for bar in bars[-bar_count:]:
                result.append({
                    "Date": bar.date,
                    "Open": bar.open,
                    "High": bar.high,
                    "Low": bar.low,
                    "Close": bar.close,
                    "Volume": bar.volume,
                    "Average": bar.average,
                    "BarCount": bar.barCount
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting bars: {e}")
            return None
    
    def subscribe_bars(self, callback: Callable) -> bool:
        """Subscribe to real-time bars"""
        try:
            if not self.es_contract:
                return False
            
            bars = self.ib.reqRealTimeBars(
                contract=self.es_contract,
                barSize=5,  # 5 second bars
                whatToShow='TRADES',
                useRTH=self.config.USE_RTH_ONLY
            )
            
            bars.updateEvent += callback
            return True
            
        except Exception as e:
            self.logger.error(f"Error subscribing to bars: {e}")
            return False
    
    # ========================================================================
    # ACCOUNT & POSITIONS
    # ========================================================================
    
    def get_account_summary(self) -> Optional[Dict[str, Any]]:
        """Get account summary"""
        try:
            summary = self.ib.accountSummary(self.account_id)
            
            result = {}
            for item in summary:
                result[item.tag] = {
                    "value": item.value,
                    "currency": item.currency
                }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting account summary: {e}")
            return None
    
    def get_positions(self) -> List[Position]:
        """Get current positions"""
        try:
            ib_positions = self.ib.positions(self.account_id)
            
            positions = []
            for pos in ib_positions:
                if pos.contract.symbol == self.config.SYMBOL:
                    side = "Long" if pos.position > 0 else "Short"
                    positions.append(Position(
                        symbol=pos.contract.localSymbol or pos.contract.symbol,
                        quantity=abs(int(pos.position)),
                        average_price=pos.avgCost / 50,  # ES multiplier is 50
                        market_value=0.0,  # Would need market data
                        unrealized_pnl=0.0,  # Would need PnL subscription
                        side=side
                    ))
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []
    
    def get_es_position(self) -> Optional[Position]:
        """Get current ES position"""
        positions = self.get_positions()
        for pos in positions:
            if self.config.SYMBOL in pos.symbol:
                return pos
        return None
    
    def get_unrealized_pnl(self) -> float:
        """Get unrealized PnL for all positions"""
        try:
            pnl = self.ib.pnl(self.account_id)
            if pnl:
                return pnl[0].unrealizedPnL or 0.0
            return 0.0
        except Exception as e:
            self.logger.error(f"Error getting PnL: {e}")
            return 0.0
    
    # ========================================================================
    # ORDERS
    # ========================================================================
    
    def place_market_order(
        self,
        action: OrderAction,
        quantity: int
    ) -> Optional[Trade]:
        """Place a market order"""
        try:
            if not self.es_contract:
                return None
            
            order = MarketOrder(
                action=action.value,
                totalQuantity=quantity,
                account=self.account_id
            )
            
            self.logger.info(f"Placing market order: {action.value} {quantity} ES")
            
            trade = self.ib.placeOrder(self.es_contract, order)
            self.ib.sleep(1)  # Wait for order to be acknowledged
            
            return trade
            
        except Exception as e:
            self.logger.error(f"Error placing market order: {e}")
            return None
    
    def place_limit_order(
        self,
        action: OrderAction,
        quantity: int,
        limit_price: float
    ) -> Optional[Trade]:
        """Place a limit order"""
        try:
            if not self.es_contract:
                return None
            
            order = LimitOrder(
                action=action.value,
                totalQuantity=quantity,
                lmtPrice=limit_price,
                account=self.account_id
            )
            
            self.logger.info(f"Placing limit order: {action.value} {quantity} ES @ {limit_price}")
            
            trade = self.ib.placeOrder(self.es_contract, order)
            self.ib.sleep(1)
            
            return trade
            
        except Exception as e:
            self.logger.error(f"Error placing limit order: {e}")
            return None
    
    def place_stop_order(
        self,
        action: OrderAction,
        quantity: int,
        stop_price: float
    ) -> Optional[Trade]:
        """Place a stop order"""
        try:
            if not self.es_contract:
                return None
            
            order = StopOrder(
                action=action.value,
                totalQuantity=quantity,
                stopPrice=stop_price,
                account=self.account_id
            )
            
            self.logger.info(f"Placing stop order: {action.value} {quantity} ES @ {stop_price}")
            
            trade = self.ib.placeOrder(self.es_contract, order)
            self.ib.sleep(1)
            
            return trade
            
        except Exception as e:
            self.logger.error(f"Error placing stop order: {e}")
            return None
    
    def place_bracket_order(
        self,
        action: OrderAction,
        quantity: int,
        entry_price: Optional[float],
        stop_loss_price: float,
        take_profit_price: float,
        entry_type: str = "MKT"
    ) -> Optional[List[Trade]]:
        """
        Place a bracket order (entry + stop loss + take profit)
        
        Args:
            action: BUY or SELL
            quantity: Number of contracts
            entry_price: Limit price for entry (None for market)
            stop_loss_price: Stop loss price
            take_profit_price: Take profit limit price
            entry_type: "MKT" or "LMT"
        """
        try:
            if not self.es_contract:
                return None
            
            # Create bracket order
            bracket = self.ib.bracketOrder(
                action=action.value,
                quantity=quantity,
                limitPrice=entry_price if entry_type == "LMT" else 0,
                takeProfitPrice=take_profit_price,
                stopLossPrice=stop_loss_price
            )
            
            # If market entry, modify the parent order
            if entry_type == "MKT":
                bracket[0].orderType = "MKT"
                bracket[0].lmtPrice = 0
            
            # Set account
            for order in bracket:
                order.account = self.account_id
            
            self.logger.info(
                f"Placing bracket order: {action.value} {quantity} ES | "
                f"SL: {stop_loss_price} | TP: {take_profit_price}"
            )
            
            # Place all orders
            trades = []
            for order in bracket:
                trade = self.ib.placeOrder(self.es_contract, order)
                trades.append(trade)
            
            self.ib.sleep(1)
            
            return trades
            
        except Exception as e:
            self.logger.error(f"Error placing bracket order: {e}")
            return None
    
    def place_oco_order(
        self,
        quantity: int,
        stop_loss_price: float,
        take_profit_price: float,
        is_long: bool = True
    ) -> Optional[List[Trade]]:
        """
        Place OCO (One-Cancels-Other) order for exit
        
        Args:
            quantity: Number of contracts
            stop_loss_price: Stop loss price
            take_profit_price: Take profit price
            is_long: True if closing a long position, False for short
        """
        try:
            if not self.es_contract:
                return None
            
            # Determine exit action
            exit_action = "SELL" if is_long else "BUY"
            
            # Create OCO group ID
            oco_group = f"OCO_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Stop loss order
            stop_order = StopOrder(
                action=exit_action,
                totalQuantity=quantity,
                stopPrice=stop_loss_price,
                account=self.account_id,
                ocaGroup=oco_group,
                ocaType=1  # Cancel all remaining orders with block
            )
            
            # Take profit order
            limit_order = LimitOrder(
                action=exit_action,
                totalQuantity=quantity,
                lmtPrice=take_profit_price,
                account=self.account_id,
                ocaGroup=oco_group,
                ocaType=1
            )
            
            self.logger.info(
                f"Placing OCO order: {exit_action} {quantity} ES | "
                f"SL: {stop_loss_price} | TP: {take_profit_price}"
            )
            
            trades = []
            trades.append(self.ib.placeOrder(self.es_contract, stop_order))
            trades.append(self.ib.placeOrder(self.es_contract, limit_order))
            
            self.ib.sleep(1)
            
            return trades
            
        except Exception as e:
            self.logger.error(f"Error placing OCO order: {e}")
            return None
    
    def cancel_order(self, trade: Trade) -> bool:
        """Cancel an order"""
        try:
            self.ib.cancelOrder(trade.order)
            self.ib.sleep(0.5)
            
            self.logger.info(f"Cancelled order: {trade.order.orderId}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error cancelling order: {e}")
            return False
    
    def cancel_all_orders(self) -> bool:
        """Cancel all open orders"""
        try:
            self.ib.reqGlobalCancel()
            self.ib.sleep(1)
            
            self.logger.info("Cancelled all orders")
            return True
            
        except Exception as e:
            self.logger.error(f"Error cancelling all orders: {e}")
            return False
    
    def get_open_orders(self) -> List[Trade]:
        """Get all open orders"""
        try:
            return self.ib.openTrades()
        except Exception as e:
            self.logger.error(f"Error getting open orders: {e}")
            return []
    
    def flatten_position(self) -> bool:
        """Flatten (close) ES position"""
        try:
            position = self.get_es_position()
            
            if not position or position.quantity == 0:
                self.logger.info("No position to flatten")
                return True
            
            # Determine action to close
            if position.side == "Long":
                action = OrderAction.SELL
            else:
                action = OrderAction.BUY
            
            # Cancel any existing orders first
            self.cancel_all_orders()
            
            # Place market order to close
            trade = self.place_market_order(action, position.quantity)
            
            if trade:
                self.logger.info(f"Flattened position: {position.quantity} {position.symbol}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error flattening position: {e}")
            return False
    
    # ========================================================================
    # UTILITIES
    # ========================================================================
    
    def sleep(self, seconds: float):
        """Sleep while processing IB events"""
        self.ib.sleep(seconds)
    
    def wait_for_fill(self, trade: Trade, timeout: int = 30) -> bool:
        """Wait for an order to fill"""
        start = time.time()
        while time.time() - start < timeout:
            self.ib.sleep(0.5)
            if trade.orderStatus.status == "Filled":
                return True
            if trade.orderStatus.status in ["Cancelled", "ApiCancelled", "Inactive"]:
                return False
        return False
