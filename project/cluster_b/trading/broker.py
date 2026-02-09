"""
Alpaca Broker Integration Module

Config example (environment variables):
    export ALPACA_API_KEY="your_api_key"
    export ALPACA_SECRET_KEY="your_secret_key"
    export ALPACA_PAPER=true  # Set to "false" for live trading

Or pass credentials directly:
    broker = AlpacaBroker(
        api_key="your_api_key",
        secret_key="your_secret_key",
        paper=True
    )

Risk Management Settings:
    - Max position: 1-2% of portfolio
    - Stop loss: 15%
    - Max 10 concurrent positions
    - Max 25% total risk
"""

import logging
import os
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pandas as pd

try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, StopLossRequest, TakeProfitRequest

    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    TradingClient = None
    MarketOrderRequest = None
    LimitOrderRequest = None
    StopLossRequest = None
    TakeProfitRequest = None
    OrderSide = None
    TimeInForce = None
    StockHistoricalDataClient = None
    StockBarsRequest = None
    TimeFrame = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class AlpacaBroker:
    """
    Alpaca broker integration for trading US stocks/options.

    Supports both paper trading (default) and live trading.
    """

    MAX_POSITIONS = 10
    MAX_POSITION_PERCENT = 0.02  # 2% of portfolio
    STOP_LOSS_PERCENT = 0.15  # 15%
    MAX_TOTAL_RISK = 0.25  # 25% of portfolio

    @staticmethod
    def _load_credentials_from_vault() -> Dict[str, Optional[str]]:
        """Read Alpaca credentials from Vault when env vars are not populated."""
        vault_url = os.getenv("VAULT_URL")
        vault_token = os.getenv("VAULT_TOKEN")
        if not vault_url or not vault_token:
            return {"api_key": None, "secret_key": None}

        try:
            import hvac

            client = hvac.Client(url=vault_url, token=vault_token)
            if not client.is_authenticated():
                return {"api_key": None, "secret_key": None}

            secret = client.read("secret/data/alpaca")
            if not secret or "data" not in secret:
                return {"api_key": None, "secret_key": None}

            secret_data = secret["data"].get("data", {})
            return {
                "api_key": secret_data.get("api_key"),
                "secret_key": secret_data.get("secret_key"),
            }
        except Exception as exc:
            logger.warning(f"Unable to load Alpaca credentials from Vault: {exc}")
            return {"api_key": None, "secret_key": None}

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: bool = True,
        demo: bool = False,
    ):
        """
        Initialize Alpaca broker client.

        Args:
            api_key: Alpaca API key. If None, reads from ALPACA_API_KEY env var.
            secret_key: Alpaca secret key. If None, reads from ALPACA_SECRET_KEY env var.
            paper: Use paper trading API. Defaults to True.
            demo: Use demo mode with mock data. Defaults to False.
        """
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        if not self.api_key or not self.secret_key:
            vault_credentials = self._load_credentials_from_vault()
            self.api_key = self.api_key or vault_credentials["api_key"]
            self.secret_key = self.secret_key or vault_credentials["secret_key"]
        self.paper = paper
        self.demo = demo or (not self.api_key or not self.secret_key)
        self._demo_open_orders: List[dict] = []
        self._demo_filled_orders: List[dict] = []
        self._demo_positions: List[dict] = []
        self._demo_account: Dict[str, Any] = {}

        if self.demo:
            logger.info("Running in DEMO mode with mock data")
            self.trading_client = None
            self.data_client = None
            self._initialize_demo_state()
            return

        if not ALPACA_AVAILABLE:
            raise ImportError("alpaca-py is required for non-demo broker usage")

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "API key and secret key are required. "
                "Pass them directly or set ALPACA_API_KEY and ALPACA_SECRET_KEY env vars."
            )

        base_url = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        logger.info(f"Connecting to Alpaca ({'paper' if paper else 'live'} trading) at {base_url}")

        try:
            self.trading_client = TradingClient(api_key=self.api_key, secret_key=self.secret_key, paper=paper)
            self.data_client = StockHistoricalDataClient(api_key=self.api_key, secret_key=self.secret_key)
            logger.info("Successfully connected to Alpaca")
        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            raise

    def _initialize_demo_state(self) -> None:
        """Initialize mutable demo account, position, and order state."""
        self._demo_account = {
            "id": "demo-account-001",
            "account_number": "PA12345678",
            "status": "ACTIVE",
            "currency": "USD",
            "cash": 75000.00,
            "portfolio_value": 100000.00,
            "buying_power": 150000.00,
            "daytrading_buying_power": 300000.00,
            "equity": 100000.00,
            "last_equity": 98500.00,
            "multiplier": 4,
            "pattern_day_trader": False,
            "trading_blocked": False,
            "transfers_blocked": False,
            "account_blocked": False,
            "trade_suspended_by_user": False,
        }
        self._demo_positions = [
            {
                "symbol": "AAPL",
                "qty": 50.0,
                "avg_entry_price": 175.50,
                "side": "long",
                "market_value": 9125.00,
                "cost_basis": 8775.00,
                "unrealized_pl": 350.00,
                "unrealized_plpc": 0.0399,
                "current_price": 182.50,
                "change_today": 0.015,
            },
            {
                "symbol": "NVDA",
                "qty": 20.0,
                "avg_entry_price": 480.00,
                "side": "long",
                "market_value": 10200.00,
                "cost_basis": 9600.00,
                "unrealized_pl": 600.00,
                "unrealized_plpc": 0.0625,
                "current_price": 510.00,
                "change_today": 0.025,
            },
            {
                "symbol": "MSFT",
                "qty": 30.0,
                "avg_entry_price": 375.00,
                "side": "long",
                "market_value": 11850.00,
                "cost_basis": 11250.00,
                "unrealized_pl": 600.00,
                "unrealized_plpc": 0.0533,
                "current_price": 395.00,
                "change_today": -0.008,
            },
        ]
        self._recalculate_demo_account()

    def _recalculate_demo_account(self) -> None:
        """Recompute demo account balances from the mutable position state."""
        positions_value = sum(float(pos["market_value"]) for pos in self._demo_positions)
        cash = float(self._demo_account.get("cash", 0.0))
        portfolio_value = cash + positions_value
        self._demo_account["portfolio_value"] = portfolio_value
        self._demo_account["equity"] = portfolio_value
        self._demo_account["buying_power"] = cash * 2
        self._demo_account["daytrading_buying_power"] = cash * 4

    def _copy_demo_order(self, order: dict) -> dict:
        """Return a copy of mutable demo order data."""
        return deepcopy(order)

    def _create_demo_order(
        self,
        *,
        symbol: str,
        qty: int,
        side: str,
        order_type: str,
        status: str,
        price: Optional[float] = None,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> dict:
        """Create a normalized demo order payload."""
        now = datetime.now().isoformat()
        return {
            "id": f"demo-{uuid4()}",
            "client_order_id": f"demo-client-{uuid4()}",
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "status": status,
            "qty": float(qty),
            "filled_qty": float(qty) if status == "filled" else 0.0,
            "filled_avg_price": (float(price) if price is not None and status == "filled" else None),
            "limit_price": float(limit_price) if limit_price is not None else None,
            "stop_price": float(stop_price) if stop_price is not None else None,
            "time_in_force": time_in_force,
            "created_at": now,
            "updated_at": now,
            "submitted_at": now,
            "filled_at": now if status == "filled" else None,
        }

    def _apply_demo_fill(self, symbol: str, qty: int, side: str, price: float) -> None:
        """Apply a filled demo market order to the in-memory portfolio."""
        existing = self.get_position(symbol)
        cash_delta = qty * price

        if side.lower() == "buy":
            self._demo_account["cash"] = float(self._demo_account["cash"]) - cash_delta
            if existing:
                new_qty = float(existing["qty"]) + qty
                total_cost = (float(existing["avg_entry_price"]) * float(existing["qty"])) + cash_delta
                existing["qty"] = new_qty
                existing["avg_entry_price"] = total_cost / new_qty
                existing["cost_basis"] = existing["avg_entry_price"] * new_qty
                existing["market_value"] = new_qty * price
                existing["current_price"] = price
                existing["unrealized_pl"] = existing["market_value"] - existing["cost_basis"]
                existing["unrealized_plpc"] = (
                    existing["unrealized_pl"] / existing["cost_basis"] if existing["cost_basis"] else 0.0
                )
            else:
                cost_basis = qty * price
                self._demo_positions.append(
                    {
                        "symbol": symbol,
                        "qty": float(qty),
                        "avg_entry_price": float(price),
                        "side": "long",
                        "market_value": cost_basis,
                        "cost_basis": cost_basis,
                        "unrealized_pl": 0.0,
                        "unrealized_plpc": 0.0,
                        "current_price": float(price),
                        "change_today": 0.0,
                    }
                )
        else:
            self._demo_account["cash"] = float(self._demo_account["cash"]) + cash_delta
            if not existing:
                raise ValueError(f"No position found for {symbol}")
            remaining_qty = float(existing["qty"]) - qty
            if remaining_qty < 0:
                raise ValueError(f"Cannot sell {qty} shares of {symbol}; only {existing['qty']} available")
            if remaining_qty == 0:
                self._demo_positions = [pos for pos in self._demo_positions if pos["symbol"] != symbol]
            else:
                existing["qty"] = remaining_qty
                existing["cost_basis"] = float(existing["avg_entry_price"]) * remaining_qty
                existing["market_value"] = remaining_qty * price
                existing["current_price"] = price
                existing["unrealized_pl"] = existing["market_value"] - existing["cost_basis"]
                existing["unrealized_plpc"] = (
                    existing["unrealized_pl"] / existing["cost_basis"] if existing["cost_basis"] else 0.0
                )

        self._recalculate_demo_account()

    def get_account(self) -> dict:
        """
        Get account information.

        Returns:
            Dict containing account details (balance, buying power, etc.)
        """
        if self.demo:
            return deepcopy(self._demo_account)

        try:
            account = self.trading_client.get_account()
            return {
                "id": account.id,
                "account_number": account.account_number,
                "status": account.status,
                "currency": account.currency,
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "buying_power": float(account.buying_power),
                "daytrading_buying_power": float(account.daytrading_buying_power),
                "equity": float(account.equity),
                "last_equity": float(account.last_equity),
                "multiplier": int(account.multiplier),
                "pattern_day_trader": account.pattern_day_trader,
                "trading_blocked": account.trading_blocked,
                "transfers_blocked": account.transfers_blocked,
                "account_blocked": account.account_blocked,
                "trade_suspended_by_user": account.trade_suspended_by_user,
            }
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            raise

    def get_positions(self) -> List[dict]:
        """
        Get all current positions.

        Returns:
            List of position dictionaries.
        """
        if self.demo:
            return deepcopy(self._demo_positions)

        try:
            positions = self.trading_client.get_all_positions()
            return [
                {
                    "symbol": pos.symbol,
                    "qty": float(pos.qty),
                    "avg_entry_price": float(pos.avg_entry_price),
                    "side": pos.side,
                    "market_value": float(pos.market_value),
                    "cost_basis": float(pos.cost_basis),
                    "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_plpc": float(pos.unrealized_plpc),
                    "current_price": float(pos.current_price),
                    "change_today": float(pos.change_today),
                }
                for pos in positions
            ]
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            raise

    def get_position(self, symbol: str) -> Optional[dict]:
        """
        Get position for a specific symbol.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Position dict or None if not found.
        """
        if self.demo:
            for pos in self._demo_positions:
                if pos["symbol"] == symbol:
                    return pos
            return None

        try:
            position = self.trading_client.get_position(symbol)
            return {
                "symbol": position.symbol,
                "qty": float(position.qty),
                "avg_entry_price": float(position.avg_entry_price),
                "side": position.side,
                "market_value": float(position.market_value),
                "cost_basis": float(position.cost_basis),
                "unrealized_pl": float(position.unrealized_pl),
                "unrealized_plpc": float(position.unrealized_plpc),
                "current_price": float(position.current_price),
                "change_today": float(position.change_today),
            }
        except Exception as e:
            if "position not found" in str(e).lower():
                return None
            logger.error(f"Failed to get position for {symbol}: {e}")
            raise

    def get_pending_orders(self) -> List[dict]:
        """
        Get all pending orders.

        Returns:
            List of pending order dictionaries.
        """
        if self.demo:
            return [self._copy_demo_order(order) for order in self._demo_open_orders]

        try:
            orders = self.trading_client.get_orders(status="open")
            return [
                {
                    "id": order.id,
                    "client_order_id": order.client_order_id,
                    "symbol": order.symbol,
                    "side": order.side,
                    "type": order.type,
                    "status": order.status,
                    "qty": float(order.qty),
                    "filled_qty": float(order.filled_qty),
                    "filled_avg_price": (float(order.filled_avg_price) if order.filled_avg_price else None),
                    "limit_price": (float(order.limit_price) if order.limit_price else None),
                    "stop_price": float(order.stop_price) if order.stop_price else None,
                    "time_in_force": order.time_in_force,
                    "created_at": str(order.created_at),
                    "updated_at": str(order.updated_at),
                }
                for order in orders
            ]
        except Exception as e:
            logger.error(f"Failed to get pending orders: {e}")
            raise

    def get_filled_orders(self, limit: int = 50) -> List[dict]:
        """Get recently filled orders."""
        if self.demo:
            return [
                self._copy_demo_order(order)
                for order in sorted(
                    self._demo_filled_orders,
                    key=lambda order: order["created_at"],
                    reverse=True,
                )[:limit]
            ]

        try:
            orders = self.trading_client.get_orders(status="closed", limit=limit)
            return [
                {
                    "id": order.id,
                    "symbol": order.symbol,
                    "side": order.side,
                    "qty": float(order.qty),
                    "filled_avg_price": (float(order.filled_avg_price) if order.filled_avg_price else 0.0),
                    "status": order.status,
                    "submitted_at": str(order.created_at),
                    "filled_at": (str(order.filled_at) if getattr(order, "filled_at", None) else None),
                }
                for order in orders
            ]
        except Exception as e:
            logger.error(f"Failed to get filled orders: {e}")
            raise

    def submit_market_order(self, symbol: str, qty: int, side: str, time_in_force: str = "day") -> dict:
        """
        Submit a market order.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            qty: Number of shares
            side: 'buy' or 'sell'
            time_in_force: Time in force ('day', 'gtc', 'ioc', 'fok')

        Returns:
            Order details dictionary.
        """
        if self.demo:
            position = self.get_position(symbol)
            execution_price = float(position["current_price"]) if position else 100.0
            order = self._create_demo_order(
                symbol=symbol,
                qty=qty,
                side=side.lower(),
                order_type="market",
                status="filled",
                price=execution_price,
                time_in_force=time_in_force,
            )
            self._apply_demo_fill(symbol, qty, side, execution_price)
            self._demo_filled_orders.append(order)
            logger.info(f"Demo market order filled: {side.upper()} {qty} {symbol}")
            return self._copy_demo_order(order)

        try:
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            tif = TimeInForce(time_in_force)

            market_order = MarketOrderRequest(symbol=symbol, qty=qty, side=order_side, time_in_force=tif)

            order = self.trading_client.submit_order(order_request=market_order)
            logger.info(f"Market order submitted: {side.upper()} {qty} {symbol}")

            return {
                "id": order.id,
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "side": order.side,
                "type": order.type,
                "status": order.status,
                "qty": float(order.qty),
                "filled_qty": float(order.filled_qty),
                "time_in_force": order.time_in_force,
                "created_at": str(order.created_at),
            }
        except Exception as e:
            logger.error(f"Failed to submit market order for {symbol}: {e}")
            raise

    def submit_limit_order(
        self,
        symbol: str,
        qty: int,
        limit_price: float,
        side: str,
        stop_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> dict:
        """
        Submit a limit order with optional stop loss.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            qty: Number of shares
            limit_price: Limit price for the order
            side: 'buy' or 'sell'
            stop_price: Optional stop price
            time_in_force: Time in force ('day', 'gtc', 'ioc', 'fok')

        Returns:
            Order details dictionary.
        """
        if self.demo:
            order = self._create_demo_order(
                symbol=symbol,
                qty=qty,
                side=side.lower(),
                order_type="limit",
                status="open",
                limit_price=limit_price,
                stop_price=stop_price,
                time_in_force=time_in_force,
            )
            self._demo_open_orders.append(order)
            logger.info(f"Demo limit order queued: {side.upper()} {qty} {symbol} @ ${limit_price}")
            return self._copy_demo_order(order)

        try:
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            tif = TimeInForce(time_in_force)

            order_params = {
                "symbol": symbol,
                "qty": qty,
                "side": order_side,
                "time_in_force": tif,
                "limit_price": limit_price,
            }

            if stop_price:
                order_params["stop_price"] = stop_price
                order_params["order_class"] = "bracket"

            limit_order = LimitOrderRequest(**order_params)
            order = self.trading_client.submit_order(order_request=limit_order)
            logger.info(f"Limit order submitted: {side.upper()} {qty} {symbol} @ ${limit_price}")

            return {
                "id": order.id,
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "side": order.side,
                "type": order.type,
                "status": order.status,
                "qty": float(order.qty),
                "limit_price": float(order.limit_price) if order.limit_price else None,
                "stop_price": float(order.stop_price) if order.stop_price else None,
                "time_in_force": order.time_in_force,
                "created_at": str(order.created_at),
            }
        except Exception as e:
            logger.error(f"Failed to submit limit order for {symbol}: {e}")
            raise

    def submit_stop_order(
        self,
        symbol: str,
        qty: int,
        stop_price: float,
        side: str,
        limit_price: Optional[float] = None,
        time_in_force: str = "gtc",
    ) -> dict:
        """
        Submit a stop order (stop loss).

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            qty: Number of shares
            stop_price: Stop price
            side: 'buy' or 'sell'
            limit_price: Optional limit price for stop-limit orders
            time_in_force: Time in force (default 'gtc' for stop orders)

        Returns:
            Order details dictionary.
        """
        if self.demo:
            order = self._create_demo_order(
                symbol=symbol,
                qty=qty,
                side=side.lower(),
                order_type="stop",
                status="open",
                stop_price=stop_price,
                limit_price=limit_price,
                time_in_force=time_in_force,
            )
            self._demo_open_orders.append(order)
            logger.info(f"Demo stop order queued: {side.upper()} {qty} {symbol} @ ${stop_price}")
            return self._copy_demo_order(order)

        try:
            from alpaca.trading.requests import StopOrderRequest

            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            tif = TimeInForce(time_in_force)

            order_params = {
                "symbol": symbol,
                "qty": qty,
                "side": order_side,
                "time_in_force": tif,
                "stop_price": stop_price,
            }

            if limit_price:
                order_params["type"] = "stop_limit"
                order_params["limit_price"] = limit_price

            stop_order = StopOrderRequest(**order_params)
            order = self.trading_client.submit_order(order_request=stop_order)
            logger.info(f"Stop order submitted: {side.upper()} {qty} {symbol} @ ${stop_price}")

            return {
                "id": order.id,
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "side": order.side,
                "type": order.type,
                "status": order.status,
                "qty": float(order.qty),
                "stop_price": float(order.stop_price) if order.stop_price else None,
                "limit_price": float(order.limit_price) if order.limit_price else None,
                "time_in_force": order.time_in_force,
                "created_at": str(order.created_at),
            }
        except Exception as e:
            logger.error(f"Failed to submit stop order for {symbol}: {e}")
            raise

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order by ID.

        Args:
            order_id: The order ID to cancel.

        Returns:
            True if cancellation successful.
        """
        if self.demo:
            remaining_orders = [order for order in self._demo_open_orders if order["id"] != order_id]
            if len(remaining_orders) == len(self._demo_open_orders):
                raise ValueError(f"Order not found: {order_id}")
            self._demo_open_orders = remaining_orders
            logger.info(f"Demo order cancelled: {order_id}")
            return True

        try:
            self.trading_client.cancel_order(order_id)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise

    def submit_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> dict:
        """Submit an order using a simple route-friendly contract."""
        normalized_order_type = order_type.lower()

        if normalized_order_type == "market":
            return self.submit_market_order(symbol, qty, side, time_in_force=time_in_force)
        if normalized_order_type == "limit":
            if limit_price is None:
                raise ValueError("limit_price is required for limit orders")
            return self.submit_limit_order(
                symbol=symbol,
                qty=qty,
                limit_price=limit_price,
                side=side,
                stop_price=stop_price,
                time_in_force=time_in_force,
            )
        if normalized_order_type == "stop":
            if stop_price is None:
                raise ValueError("stop_price is required for stop orders")
            return self.submit_stop_order(
                symbol=symbol,
                qty=qty,
                stop_price=stop_price,
                side=side,
                limit_price=limit_price,
                time_in_force=time_in_force,
            )

        raise ValueError(f"Unsupported order_type: {order_type}")

    def get_bars(
        self,
        symbol: str,
        timeframe: str = "1H",
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """
        Get historical bar data for a symbol.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            timeframe: Time frame ('1Min', '5Min', '15Min', '1H', '1D')
            start: Start date (ISO format, e.g., '2024-01-01')
            end: End date (ISO format, e.g., '2024-12-31')
            limit: Maximum number of bars to return

        Returns:
            DataFrame with OHLCV data.
        """
        try:
            timeframe_map = {
                "1Min": TimeFrame.Minute,
                "5Min": TimeFrame.Minute,
                "15Min": TimeFrame.Minute,
                "1H": TimeFrame.Hour,
                "1D": TimeFrame.Day,
            }

            tf = timeframe_map.get(timeframe, TimeFrame.Hour)

            if not start:
                from datetime import timedelta

                start = (datetime.now() - timedelta(days=30)).isoformat()
            if not end:
                end = datetime.now().isoformat()

            request_params = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                start=start,
                end=end,
                limit=limit,
            )

            bars = self.data_client.get_stock_bars(request_params)

            if hasattr(bars, "df") and bars.df is not None:
                df = bars.df
                if isinstance(df.index, pd.MultiIndex):
                    df = df.xs(symbol, level=1)
                return df

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Failed to get bars for {symbol}: {e}")
            raise

    def is_market_open(self) -> bool:
        """
        Check if the market is currently open.

        Returns:
            True if market is open.
        """
        try:
            clock = self.trading_client.get_clock()
            return clock.is_open
        except Exception as e:
            if self.demo:
                return True
            logger.error(f"Failed to check market status: {e}")
            raise

    def get_max_position_size(self) -> float:
        """
        Calculate maximum position size based on portfolio value.

        Returns:
            Maximum dollar amount to risk per position.
        """
        try:
            account = self.get_account()
            portfolio_value = float(account["portfolio_value"])
            return portfolio_value * self.MAX_POSITION_PERCENT
        except Exception as e:
            logger.error(f"Failed to calculate max position size: {e}")
            raise

    def get_current_risk(self) -> float:
        """
        Calculate current total risk exposure.

        Returns:
            Current risk as a percentage of portfolio.
        """
        try:
            positions = self.get_positions()
            account = self.get_account()
            portfolio_value = float(account["portfolio_value"])

            total_risk = 0.0
            for pos in positions:
                unrealized_pl = abs(float(pos["unrealized_pl"]))
                total_risk += unrealized_pl

            return total_risk / portfolio_value if portfolio_value > 0 else 0.0
        except Exception as e:
            logger.error(f"Failed to calculate current risk: {e}")
            raise

    def can_open_position(self) -> bool:
        """
        Check if a new position can be opened based on risk limits.

        Returns:
            True if a new position can be opened.
        """
        try:
            positions = self.get_positions()
            current_risk = self.get_current_risk()

            if len(positions) >= self.MAX_POSITIONS:
                logger.warning(f"Max positions reached: {len(positions)}/{self.MAX_POSITIONS}")
                return False

            if current_risk >= self.MAX_TOTAL_RISK:
                logger.warning(f"Max total risk reached: {current_risk:.2%}/{self.MAX_TOTAL_RISK:.2%}")
                return False

            return True
        except Exception as e:
            logger.error(f"Failed to check position eligibility: {e}")
            raise

    def close_position(self, symbol: str, qty: Optional[int] = None) -> dict:
        """
        Close a position (or partial close).

        Args:
            symbol: Stock symbol to close
            qty: Optional quantity to close (closes all if not specified)

        Returns:
            Order details.
        """
        try:
            position = self.get_position(symbol)
            if not position:
                raise ValueError(f"No position found for {symbol}")

            close_qty = qty if qty else int(float(position["qty"]))
            side = "sell" if position["side"] == "long" else "buy"

            return self.submit_market_order(symbol, close_qty, side)
        except Exception as e:
            logger.error(f"Failed to close position for {symbol}: {e}")
            raise

    def close_all_positions(self) -> List[dict]:
        """
        Close all open positions.

        Returns:
            List of order details.
        """
        try:
            positions = self.get_positions()
            orders = []
            for pos in positions:
                order = self.close_position(pos["symbol"])
                orders.append(order)
            return orders
        except Exception as e:
            logger.error(f"Failed to close all positions: {e}")
            raise


def create_broker(paper: bool = True) -> AlpacaBroker:
    """
    Factory function to create an Alpaca broker instance.

    Args:
        paper: Use paper trading (default True)

    Returns:
        AlpacaBroker instance
    """
    return AlpacaBroker(paper=paper)


if __name__ == "__main__":
    import json

    broker = create_broker(paper=True)

    print("=== Account Info ===")
    print(json.dumps(broker.get_account(), indent=2, default=str))

    print("\n=== Market Status ===")
    print(f"Market open: {broker.is_market_open()}")

    print("\n=== Positions ===")
    print(json.dumps(broker.get_positions(), indent=2, default=str))

    print("\n=== Pending Orders ===")
    print(json.dumps(broker.get_pending_orders(), indent=2, default=str))
