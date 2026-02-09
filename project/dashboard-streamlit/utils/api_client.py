"""
Trading API Client
Wrapper for FastAPI trading endpoints
"""

import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class TradingAPIClient:
    """Client for interacting with the Trading API"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make API request"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    # Health
    def get_health(self) -> Dict:
        """Get API health status"""
        return self._request("GET", "/health")

    # Account
    def get_account(self) -> Dict:
        """Get account information"""
        return self._request("GET", "/account/")

    def get_portfolio(self) -> Dict:
        """Get portfolio summary"""
        return self._request("GET", "/account/portfolio")

    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """Get trade history"""
        return self._request("GET", "/account/history", params={"limit": limit})

    # Signals
    def get_signal(self, symbol: str) -> Dict:
        """Get signal for a symbol"""
        return self._request("GET", f"/trading/signals/{symbol}")

    def get_signals_batch(self, symbols: List[str], min_confidence: float = 0.6) -> List[Dict]:
        """Get signals for multiple symbols"""
        return self._request(
            "POST",
            "/trading/signals/batch",
            json={"symbols": symbols, "min_confidence": min_confidence},
        )

    # Orders
    def get_orders(self) -> List[Dict]:
        """Get pending orders"""
        response = self._request("GET", "/trading/orders")
        return response.get("orders", [])

    def submit_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ) -> Dict:
        """Submit a trading order"""
        order_data = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "order_type": order_type,
        }
        if limit_price:
            order_data["limit_price"] = limit_price
        return self._request("POST", "/trading/orders", json=order_data)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            self._request("DELETE", f"/trading/orders/{order_id}")
            return True
        except requests.exceptions.RequestException as exc:
            logger.error("Failed to cancel order %s: %s", order_id, exc)
            return False

    # Positions
    def get_positions(self) -> List[Dict]:
        """Get open positions"""
        response = self._request("GET", "/trading/positions")
        return response.get("positions", [])

    def close_position(self, symbol: str) -> Dict:
        """Close a position"""
        return self._request("DELETE", f"/trading/positions/{symbol}")

    # Trading Cycle
    def run_trading_cycle(self, symbols: List[str]) -> Dict:
        """Run full trading cycle"""
        return self._request("POST", "/trading/cycle", json={"symbols": symbols})

    def get_pending_signals(
        self,
        symbols: List[str],
        min_confidence: float = 0.6,
    ) -> List[Dict]:
        """Return actionable BUY/SELL signals for manual review."""
        signals = self.get_signals_batch(symbols, min_confidence=min_confidence)
        return [signal for signal in signals if signal.get("signal", "HOLD").upper() in {"BUY", "SELL"}]
