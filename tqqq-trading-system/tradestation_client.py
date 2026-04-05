# TradeStation API Client for TQQQ Trading

import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from config import TradingConfig, Position, setup_logging


class TradeStationClient:
    """TradeStation API Client"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = setup_logging("TSClient")
        self.access_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self._session = requests.Session()
    
    def authenticate(self) -> bool:
        try:
            resp = requests.post(
                self.config.AUTH_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.config.API_KEY,
                    "client_secret": self.config.API_SECRET,
                    "refresh_token": self.config.REFRESH_TOKEN
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data["access_token"]
                self.token_expiry = datetime.now() + timedelta(seconds=data.get("expires_in", 1200) - 60)
                self.logger.info("Authenticated with TradeStation")
                return True
            else:
                self.logger.error(f"Auth failed: {resp.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"Auth error: {e}")
            return False
    
    def _headers(self) -> Dict[str, str]:
        if not self.access_token or datetime.now() >= self.token_expiry:
            self.authenticate()
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
    
    def get_quote(self) -> Optional[Dict]:
        try:
            resp = self._session.get(
                f"{self.config.BASE_URL}/marketdata/quotes/{self.config.SYMBOL}",
                headers=self._headers()
            )
            if resp.status_code == 200:
                quotes = resp.json().get("Quotes", [])
                return quotes[0] if quotes else None
        except Exception as e:
            self.logger.error(f"Quote error: {e}")
        return None
    
    def get_bars(self) -> Optional[List[Dict]]:
        try:
            resp = self._session.get(
                f"{self.config.BASE_URL}/marketdata/barcharts/{self.config.SYMBOL}",
                headers=self._headers(),
                params={"interval": self.config.BAR_INTERVAL, "unit": self.config.BAR_UNIT, "barsback": self.config.BARS_BACK}
            )
            if resp.status_code == 200:
                return resp.json().get("Bars", [])
        except Exception as e:
            self.logger.error(f"Bars error: {e}")
        return None
    
    def get_positions(self) -> List[Position]:
        try:
            resp = self._session.get(
                f"{self.config.BASE_URL}/brokerage/accounts/{self.config.ACCOUNT_ID}/positions",
                headers=self._headers()
            )
            if resp.status_code == 200:
                return [
                    Position(
                        symbol=p.get("Symbol", ""),
                        quantity=int(p.get("Quantity", 0)),
                        average_price=float(p.get("AveragePrice", 0)),
                        market_value=float(p.get("MarketValue", 0)),
                        unrealized_pnl=float(p.get("UnrealizedProfitLoss", 0)),
                        side=p.get("LongShort", "")
                    )
                    for p in resp.json().get("Positions", [])
                ]
        except Exception as e:
            self.logger.error(f"Positions error: {e}")
        return []
    
    def get_balances(self) -> Optional[Dict]:
        try:
            resp = self._session.get(
                f"{self.config.BASE_URL}/brokerage/accounts/{self.config.ACCOUNT_ID}/balances",
                headers=self._headers()
            )
            if resp.status_code == 200:
                balances = resp.json().get("Balances", [])
                return balances[0] if balances else None
        except Exception as e:
            self.logger.error(f"Balances error: {e}")
        return None
    
    def place_bracket_order(
        self, quantity: int, side: str, stop_loss: float, take_profit: float
    ) -> Optional[Dict]:
        try:
            exit_side = "Sell" if side in ["Buy", "BuyToCover"] else "BuyToCover"
            
            order = {
                "Type": "BRK",
                "Orders": [
                    {
                        "AccountID": self.config.ACCOUNT_ID,
                        "Symbol": self.config.SYMBOL,
                        "Quantity": str(quantity),
                        "OrderType": "Market",
                        "TradeAction": side,
                        "TimeInForce": {"Duration": "Day"},
                        "Route": "Intelligent"
                    },
                    {
                        "AccountID": self.config.ACCOUNT_ID,
                        "Symbol": self.config.SYMBOL,
                        "Quantity": str(quantity),
                        "OrderType": "StopMarket",
                        "StopPrice": str(stop_loss),
                        "TradeAction": exit_side,
                        "TimeInForce": {"Duration": "GTC"},
                        "Route": "Intelligent"
                    },
                    {
                        "AccountID": self.config.ACCOUNT_ID,
                        "Symbol": self.config.SYMBOL,
                        "Quantity": str(quantity),
                        "OrderType": "Limit",
                        "LimitPrice": str(take_profit),
                        "TradeAction": exit_side,
                        "TimeInForce": {"Duration": "GTC"},
                        "Route": "Intelligent"
                    }
                ]
            }
            
            resp = self._session.post(
                f"{self.config.BASE_URL}/orderexecution/ordergroups",
                headers=self._headers(),
                json=order
            )
            
            if resp.status_code in [200, 201]:
                self.logger.info(f"Bracket order placed: {quantity} shares")
                return resp.json()
            else:
                self.logger.error(f"Order failed: {resp.status_code} - {resp.text}")
        except Exception as e:
            self.logger.error(f"Order error: {e}")
        return None
    
    def flatten_position(self) -> bool:
        try:
            for pos in self.get_positions():
                if pos.symbol == self.config.SYMBOL and pos.quantity != 0:
                    side = "Sell" if pos.side == "Long" else "BuyToCover"
                    resp = self._session.post(
                        f"{self.config.BASE_URL}/orderexecution/orders",
                        headers=self._headers(),
                        json={
                            "AccountID": self.config.ACCOUNT_ID,
                            "Symbol": self.config.SYMBOL,
                            "Quantity": str(abs(pos.quantity)),
                            "OrderType": "Market",
                            "TradeAction": side,
                            "TimeInForce": {"Duration": "Day"},
                            "Route": "Intelligent"
                        }
                    )
                    if resp.status_code in [200, 201]:
                        self.logger.info(f"Position flattened: {pos.quantity} shares")
                        return True
        except Exception as e:
            self.logger.error(f"Flatten error: {e}")
        return False
    
    def cancel_all_orders(self) -> bool:
        try:
            resp = self._session.get(
                f"{self.config.BASE_URL}/brokerage/accounts/{self.config.ACCOUNT_ID}/orders",
                headers=self._headers()
            )
            if resp.status_code == 200:
                for order in resp.json().get("Orders", []):
                    if order.get("Status") == "Open":
                        self._session.delete(
                            f"{self.config.BASE_URL}/orderexecution/orders/{order['OrderID']}",
                            headers=self._headers()
                        )
            return True
        except Exception as e:
            self.logger.error(f"Cancel error: {e}")
        return False
