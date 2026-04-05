# TradeStation API Client
# Handles authentication and API calls

import requests
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import threading

from config import (
    TradingConfig, OrderType, OrderSide, OrderDuration,
    Position, setup_logging
)


class TradeStationClient:
    """TradeStation API Client for trading operations"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = setup_logging("TSClient")
        
        self.access_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self.refresh_token = config.REFRESH_TOKEN
        
        self._lock = threading.Lock()
        self._session = requests.Session()
        
    # ========================================================================
    # AUTHENTICATION
    # ========================================================================
    
    def authenticate(self) -> bool:
        """Authenticate with TradeStation API using refresh token"""
        try:
            payload = {
                "grant_type": "refresh_token",
                "client_id": self.config.API_KEY,
                "client_secret": self.config.API_SECRET,
                "refresh_token": self.refresh_token
            }
            
            response = requests.post(
                self.config.AUTH_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                self.refresh_token = data.get("refresh_token", self.refresh_token)
                expires_in = data.get("expires_in", 1200)
                self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
                
                self.logger.info("Successfully authenticated with TradeStation")
                return True
            else:
                self.logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Authentication error: {e}")
            return False
    
    def ensure_authenticated(self) -> bool:
        """Ensure we have a valid access token"""
        with self._lock:
            if self.access_token is None or self.token_expiry is None:
                return self.authenticate()
            
            if datetime.now() >= self.token_expiry:
                return self.authenticate()
            
            return True
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication"""
        self.ensure_authenticated()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    # ========================================================================
    # MARKET DATA
    # ========================================================================
    
    def get_quote(self, symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get current quote for a symbol"""
        try:
            sym = symbol or self.config.SYMBOL
            url = f"{self.config.BASE_URL}/marketdata/quotes/{sym}"
            response = self._session.get(url, headers=self._get_headers())
            
            if response.status_code == 200:
                data = response.json()
                if "Quotes" in data and len(data["Quotes"]) > 0:
                    return data["Quotes"][0]
            else:
                self.logger.error(f"Failed to get quote: {response.status_code}")
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting quote: {e}")
            return None
    
    def get_bars(
        self,
        symbol: Optional[str] = None,
        interval: Optional[int] = None,
        unit: Optional[str] = None,
        bars_back: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Get historical bars for a symbol"""
        try:
            sym = symbol or self.config.SYMBOL
            intv = interval or self.config.BAR_INTERVAL
            unt = unit or self.config.BAR_UNIT
            bb = bars_back or self.config.BARS_BACK
            
            url = f"{self.config.BASE_URL}/marketdata/barcharts/{sym}"
            params = {
                "interval": intv,
                "unit": unt,
                "barsback": bb
            }
            
            response = self._session.get(url, headers=self._get_headers(), params=params)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("Bars", [])
            else:
                self.logger.error(f"Failed to get bars: {response.status_code}")
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting bars: {e}")
            return None
    
    # ========================================================================
    # ACCOUNT & POSITIONS
    # ========================================================================
    
    def get_accounts(self) -> Optional[List[Dict[str, Any]]]:
        """Get list of accounts"""
        try:
            url = f"{self.config.BASE_URL}/brokerage/accounts"
            response = self._session.get(url, headers=self._get_headers())
            
            if response.status_code == 200:
                data = response.json()
                return data.get("Accounts", [])
            else:
                self.logger.error(f"Failed to get accounts: {response.status_code}")
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting accounts: {e}")
            return None
    
    def get_positions(self, account_id: Optional[str] = None) -> List[Position]:
        """Get current positions for an account"""
        try:
            acct = account_id or self.config.ACCOUNT_ID
            url = f"{self.config.BASE_URL}/brokerage/accounts/{acct}/positions"
            response = self._session.get(url, headers=self._get_headers())
            
            positions = []
            
            if response.status_code == 200:
                data = response.json()
                for pos in data.get("Positions", []):
                    positions.append(Position(
                        symbol=pos.get("Symbol", ""),
                        quantity=int(pos.get("Quantity", 0)),
                        average_price=float(pos.get("AveragePrice", 0)),
                        market_value=float(pos.get("MarketValue", 0)),
                        unrealized_pnl=float(pos.get("UnrealizedProfitLoss", 0)),
                        side=pos.get("LongShort", "")
                    ))
            else:
                self.logger.error(f"Failed to get positions: {response.status_code}")
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []
    
    def get_balances(self, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get account balances"""
        try:
            acct = account_id or self.config.ACCOUNT_ID
            url = f"{self.config.BASE_URL}/brokerage/accounts/{acct}/balances"
            response = self._session.get(url, headers=self._get_headers())
            
            if response.status_code == 200:
                data = response.json()
                return data.get("Balances", [{}])[0] if data.get("Balances") else None
            else:
                self.logger.error(f"Failed to get balances: {response.status_code}")
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting balances: {e}")
            return None
    
    # ========================================================================
    # ORDERS
    # ========================================================================
    
    def place_order(
        self,
        symbol: str,
        quantity: int,
        side: OrderSide,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        duration: OrderDuration = OrderDuration.DAY,
        account_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Place an order"""
        try:
            acct = account_id or self.config.ACCOUNT_ID
            url = f"{self.config.BASE_URL}/orderexecution/orders"
            
            order = {
                "AccountID": acct,
                "Symbol": symbol,
                "Quantity": str(quantity),
                "OrderType": order_type.value,
                "TradeAction": side.value,
                "TimeInForce": {"Duration": duration.value},
                "Route": "Intelligent"
            }
            
            if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT] and limit_price:
                order["LimitPrice"] = str(limit_price)
            
            if order_type in [OrderType.STOP_MARKET, OrderType.STOP_LIMIT] and stop_price:
                order["StopPrice"] = str(stop_price)
            
            self.logger.info(f"Placing order: {side.value} {quantity} {symbol} @ {order_type.value}")
            
            response = self._session.post(url, headers=self._get_headers(), json=order)
            
            if response.status_code in [200, 201]:
                data = response.json()
                order_id = data.get("Orders", [{}])[0].get("OrderID")
                self.logger.info(f"Order placed successfully: {order_id}")
                return data
            else:
                self.logger.error(f"Failed to place order: {response.status_code} - {response.text}")
                return None
            
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return None
    
    def place_bracket_order(
        self,
        symbol: str,
        quantity: int,
        side: OrderSide,
        stop_loss_price: float,
        take_profit_price: float,
        entry_type: OrderType = OrderType.MARKET,
        entry_price: Optional[float] = None,
        account_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Place a bracket order (entry + stop loss + take profit)"""
        try:
            acct = account_id or self.config.ACCOUNT_ID
            url = f"{self.config.BASE_URL}/orderexecution/ordergroups"
            
            # Determine exit side
            if side in [OrderSide.BUY, OrderSide.BUY_TO_COVER]:
                exit_side = OrderSide.SELL.value
            else:
                exit_side = OrderSide.BUY_TO_COVER.value
            
            order_group = {
                "Type": "BRK",  # Bracket
                "Orders": [
                    {
                        "AccountID": acct,
                        "Symbol": symbol,
                        "Quantity": str(quantity),
                        "OrderType": entry_type.value,
                        "TradeAction": side.value,
                        "TimeInForce": {"Duration": "Day"},
                        "Route": "Intelligent"
                    },
                    {
                        "AccountID": acct,
                        "Symbol": symbol,
                        "Quantity": str(quantity),
                        "OrderType": "StopMarket",
                        "StopPrice": str(stop_loss_price),
                        "TradeAction": exit_side,
                        "TimeInForce": {"Duration": "GTC"},
                        "Route": "Intelligent"
                    },
                    {
                        "AccountID": acct,
                        "Symbol": symbol,
                        "Quantity": str(quantity),
                        "OrderType": "Limit",
                        "LimitPrice": str(take_profit_price),
                        "TradeAction": exit_side,
                        "TimeInForce": {"Duration": "GTC"},
                        "Route": "Intelligent"
                    }
                ]
            }
            
            if entry_type == OrderType.LIMIT and entry_price:
                order_group["Orders"][0]["LimitPrice"] = str(entry_price)
            
            self.logger.info(
                f"Placing bracket order: {side.value} {quantity} {symbol} "
                f"SL:{stop_loss_price} TP:{take_profit_price}"
            )
            
            response = self._session.post(url, headers=self._get_headers(), json=order_group)
            
            if response.status_code in [200, 201]:
                data = response.json()
                self.logger.info(f"Bracket order placed successfully")
                return data
            else:
                self.logger.error(f"Failed to place bracket order: {response.status_code} - {response.text}")
                return None
            
        except Exception as e:
            self.logger.error(f"Error placing bracket order: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            url = f"{self.config.BASE_URL}/orderexecution/orders/{order_id}"
            response = self._session.delete(url, headers=self._get_headers())
            
            if response.status_code in [200, 204]:
                self.logger.info(f"Order {order_id} cancelled successfully")
                return True
            else:
                self.logger.error(f"Failed to cancel order: {response.status_code}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error cancelling order: {e}")
            return False
    
    def get_orders(
        self,
        account_id: Optional[str] = None,
        status: str = "Open"
    ) -> List[Dict[str, Any]]:
        """Get orders for an account"""
        try:
            acct = account_id or self.config.ACCOUNT_ID
            url = f"{self.config.BASE_URL}/brokerage/accounts/{acct}/orders"
            
            response = self._session.get(url, headers=self._get_headers())
            
            if response.status_code == 200:
                data = response.json()
                orders = data.get("Orders", [])
                
                if status:
                    orders = [o for o in orders if o.get("Status") == status]
                
                return orders
            else:
                self.logger.error(f"Failed to get orders: {response.status_code}")
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting orders: {e}")
            return []
    
    def flatten_position(
        self,
        symbol: Optional[str] = None,
        account_id: Optional[str] = None
    ) -> bool:
        """Flatten (close) all positions for a symbol"""
        try:
            sym = symbol or self.config.SYMBOL
            positions = self.get_positions(account_id)
            
            for pos in positions:
                if pos.symbol == sym and pos.quantity != 0:
                    if pos.side == "Long":
                        side = OrderSide.SELL
                    else:
                        side = OrderSide.BUY_TO_COVER
                    
                    result = self.place_order(
                        symbol=sym,
                        quantity=abs(pos.quantity),
                        side=side,
                        order_type=OrderType.MARKET,
                        account_id=account_id
                    )
                    
                    if result:
                        self.logger.info(f"Flattened position: {pos.quantity} {sym}")
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error flattening position: {e}")
            return False
    
    def cancel_all_orders(self, account_id: Optional[str] = None) -> bool:
        """Cancel all open orders"""
        try:
            orders = self.get_orders(account_id, status="Open")
            
            for order in orders:
                order_id = order.get("OrderID")
                if order_id:
                    self.cancel_order(order_id)
            
            self.logger.info(f"Cancelled {len(orders)} orders")
            return True
            
        except Exception as e:
            self.logger.error(f"Error cancelling all orders: {e}")
            return False
