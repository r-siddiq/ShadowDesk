"""
Trading Executor Module
Handles trading execution with risk management
"""

import logging
from datetime import datetime
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TradingExecutor:
    """
    Trading executor with integrated risk management.
    Combines broker execution, signal generation, and position risk controls.
    """

    def __init__(
        self,
        broker,
        signals=None,
        max_positions: int = 10,
        max_position_pct: float = 0.02,
        stop_loss_pct: float = 0.15,
        max_total_risk: float = 0.25,
        min_confidence: float = 0.6,
    ):
        """
        Initialize TradingExecutor.

        Args:
            broker: AlpacaBroker instance
            signals: TradingSignals instance (optional)
            max_positions: Maximum concurrent positions allowed
            max_position_pct: Maximum position size as % of portfolio (default 2%)
            stop_loss_pct: Stop loss percentage (default 15%)
            max_total_risk: Maximum total risk exposure (default 25%)
            min_confidence: Minimum signal confidence to execute
        """
        self.broker = broker
        self.signals = signals
        self.max_positions = max_positions
        self.max_position_pct = max_position_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_total_risk = max_total_risk
        self.min_confidence = min_confidence

        self._open_positions: Dict[str, dict] = {}
        self._order_history: List[dict] = []

        logger.info(
            f"TradingExecutor initialized: max_positions={max_positions}, "
            f"max_position_pct={max_position_pct:.1%}, stop_loss_pct={stop_loss_pct:.1%}, "
            f"max_total_risk={max_total_risk:.1%}"
        )

        self._refresh_positions()

    def _refresh_positions(self) -> None:
        """Refresh internal position tracking from broker."""
        try:
            positions = self.broker.get_positions()
            self._open_positions = {pos["symbol"]: pos for pos in positions}
            logger.info(f"Refreshed positions: {len(self._open_positions)} open")
        except Exception as e:
            logger.error(f"Failed to refresh positions: {e}")

    def get_open_positions(self) -> Dict[str, dict]:
        """Get current open positions."""
        self._refresh_positions()
        return self._open_positions.copy()

    def get_portfolio_value(self) -> float:
        """Get current portfolio value."""
        try:
            account = self.broker.get_account()
            return float(account["portfolio_value"])
        except Exception as e:
            logger.error(f"Failed to get portfolio value: {e}")
            return 0.0

    def calculate_position_size(self, price: float) -> int:
        """
        Calculate position size based on risk parameters.

        Args:
            price: Current price

        Returns asset:
            Number of shares to buy
        """
        try:
            portfolio_value = self.get_portfolio_value()
            max_position_value = portfolio_value * self.max_position_pct

            qty = int(max_position_value / price)

            min_qty = 1
            if qty < min_qty:
                logger.warning(f"Calculated qty {qty} below minimum {min_qty}, using minimum")
                return min_qty

            logger.info(
                f"Position size: {qty} shares @ ${price:.2f} "
                f"(value: ${qty * price:.2f}, {self.max_position_pct:.1%} of portfolio)"
            )
            return qty

        except Exception as e:
            logger.error(f"Failed to calculate position size: {e}")
            return 0

    def calculate_stop_loss_price(self, entry_price: float) -> float:
        """
        Calculate stop loss price based on entry price and stop loss %.

        Args:
            entry_price: Entry price of the position

        Returns:
            Stop loss price
        """
        stop_price = entry_price * (1 - self.stop_loss_pct)
        logger.info(f"Stop loss calculated: ${entry_price:.2f} -> ${stop_price:.2f} ({self.stop_loss_pct:.1%})")
        return stop_price

    def can_trade(self, symbol: str) -> Tuple[bool, str]:
        """
        Check if we can open a new position for the given symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Tuple of (can_trade: bool, reason: str)
        """
        self._refresh_positions()

        if symbol in self._open_positions:
            logger.warning(f"Cannot trade {symbol}: already in position")
            return False, "already_in_position"

        if len(self._open_positions) >= self.max_positions:
            logger.warning(
                f"Cannot trade {symbol}: max positions reached " f"({len(self._open_positions)}/{self.max_positions})"
            )
            return False, "max_positions_reached"

        try:
            current_risk = self.broker.get_current_risk()
            if current_risk >= self.max_total_risk:
                logger.warning(
                    f"Cannot trade {symbol}: max total risk reached " f"({current_risk:.1%}/{self.max_total_risk:.1%})"
                )
                return False, "max_total_risk_reached"

            account = self.broker.get_account()
            buying_power = float(account["buying_power"])
            if buying_power <= 0:
                logger.warning(f"Cannot trade {symbol}: no buying power")
                return False, "no_buying_power"

            logger.info(
                f"Can trade {symbol}: positions={len(self._open_positions)}/{self.max_positions}, "
                f"risk={current_risk:.1%}/{self.max_total_risk:.1%}"
            )
            return True, "ok"

        except Exception as e:
            logger.error(f"Error checking trade eligibility for {symbol}: {e}")
            return False, f"error: {str(e)}"

    def execute_buy(self, signal: dict) -> dict:
        """
        Execute a buy order based on a trading signal.

        Args:
            signal: Signal dict with symbol, current_price, confidence

        Returns:
            Order result dict
        """
        symbol = signal.get("symbol")
        price = signal.get("current_price", 0)
        confidence = signal.get("confidence", 0)

        logger.info(f"Executing buy for {symbol} @ ${price} (confidence: {confidence:.2f})")

        can_trade, reason = self.can_trade(symbol)
        if not can_trade:
            logger.warning(f"Buy rejected for {symbol}: {reason}")
            return {
                "status": "rejected",
                "symbol": symbol,
                "side": "buy",
                "qty": 0,
                "price": price,
                "reason": reason,
            }

        if confidence < self.min_confidence:
            logger.warning(f"Buy rejected for {symbol}: confidence {confidence:.2f} < {self.min_confidence}")
            return {
                "status": "rejected",
                "symbol": symbol,
                "side": "buy",
                "qty": 0,
                "price": price,
                "reason": f"low_confidence_{confidence:.2f}",
            }

        try:
            qty = self.calculate_position_size(price)
            if qty <= 0:
                return {
                    "status": "rejected",
                    "symbol": symbol,
                    "side": "buy",
                    "qty": 0,
                    "price": price,
                    "reason": "insufficient_buying_power",
                }

            stop_price = self.calculate_stop_loss_price(price)

            order = self.broker.submit_market_order(symbol=symbol, qty=qty, side="buy")

            self.broker.submit_stop_order(symbol=symbol, qty=qty, stop_price=stop_price, side="sell")

            result = {
                "status": "success",
                "order_id": order.get("id"),
                "symbol": symbol,
                "side": "buy",
                "qty": qty,
                "price": price,
                "stop_price": stop_price,
                "confidence": confidence,
                "reason": f"signal_confidence_{confidence:.2f}",
            }

            self._order_history.append(result)
            logger.info(f"Buy executed: {symbol} {qty} shares @ ${price}")

            return result

        except Exception as e:
            logger.error(f"Failed to execute buy for {symbol}: {e}")
            return {
                "status": "error",
                "symbol": symbol,
                "side": "buy",
                "qty": 0,
                "price": price,
                "reason": str(e),
            }

    def execute_sell(self, symbol: str, reason: str = "signal") -> dict:
        """
        Execute a sell order for an existing position.

        Args:
            symbol: Stock symbol to sell
            reason: Reason for selling (signal, stop_loss, etc.)

        Returns:
            Order result dict
        """
        logger.info(f"Executing sell for {symbol}, reason: {reason}")

        try:
            position = self.broker.get_position(symbol)
            if not position:
                logger.warning(f"No position found for {symbol}")
                return {
                    "status": "rejected",
                    "symbol": symbol,
                    "side": "sell",
                    "qty": 0,
                    "price": 0,
                    "reason": "no_position",
                }

            qty = int(float(position["qty"]))
            current_price = float(position["current_price"])
            entry_price = float(position["avg_entry_price"])

            order = self.broker.submit_market_order(symbol=symbol, qty=qty, side="sell")

            pnl = (current_price - entry_price) * qty
            pnl_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0

            result = {
                "status": "success",
                "order_id": order.get("id"),
                "symbol": symbol,
                "side": "sell",
                "qty": qty,
                "price": current_price,
                "entry_price": entry_price,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "reason": reason,
            }

            self._order_history.append(result)
            logger.info(f"Sell executed: {symbol} {qty} shares @ ${current_price}, " f"PnL: ${pnl:.2f} ({pnl_pct:.1%})")

            return result

        except Exception as e:
            logger.error(f"Failed to execute sell for {symbol}: {e}")
            return {
                "status": "error",
                "symbol": symbol,
                "side": "sell",
                "qty": 0,
                "price": 0,
                "reason": str(e),
            }

    def check_stop_loss(self, position: dict) -> bool:
        """
        Check if a position has hit its stop loss threshold.

        Args:
            position: Position dict with avg_entry_price, current_price

        Returns:
            True if stop loss triggered
        """
        try:
            symbol = position.get("symbol")
            entry_price = float(position.get("avg_entry_price", 0))
            current_price = float(position.get("current_price", 0))

            if entry_price <= 0:
                return False

            loss_pct = (entry_price - current_price) / entry_price

            if loss_pct >= self.stop_loss_pct:
                logger.warning(
                    f"Stop loss triggered for {symbol}: "
                    f"entry=${entry_price:.2f}, current=${current_price:.2f}, "
                    f"loss={loss_pct:.1%} >= {self.stop_loss_pct:.1%}"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking stop loss: {e}")
            return False

    def check_all_stop_losses(self) -> List[dict]:
        """
        Check all positions for stop loss triggers.

        Returns:
            List of positions that hit stop loss
        """
        self._refresh_positions()
        stop_loss_positions = []

        for symbol, position in self._open_positions.items():
            if self.check_stop_loss(position):
                stop_loss_positions.append({"symbol": symbol, "position": position, "reason": "stop_loss"})

        if stop_loss_positions:
            logger.info(f"Stop loss triggered for {len(stop_loss_positions)} positions")

        return stop_loss_positions

    def process_signals(self, signals: List[dict]) -> List[dict]:
        """
        Process multiple trading signals and execute orders.

        Args:
            signals: List of signal dicts from TradingSignals

        Returns:
            List of execution results
        """
        if not signals:
            logger.info("No signals to process")
            return []

        logger.info(f"Processing {len(signals)} signals")

        results = []
        for signal in signals:
            signal_type = signal.get("signal", "HOLD")
            symbol = signal.get("symbol")

            if signal_type == "BUY":
                result = self.execute_buy(signal)
            elif signal_type == "SELL":
                existing_position = self.broker.get_position(symbol)
                if existing_position:
                    result = self.execute_sell(symbol, reason="signal")
                else:
                    logger.info(f"Sell signal ignored for {symbol}: no position")
                    result = {
                        "status": "rejected",
                        "symbol": symbol,
                        "side": "sell",
                        "reason": "no_position",
                    }
            else:
                logger.debug(f"Hold signal for {symbol}, no action")
                result = {
                    "status": "skipped",
                    "symbol": symbol,
                    "reason": "hold_signal",
                }

            results.append(result)

        success_count = sum(1 for r in results if r.get("status") == "success")
        logger.info(f"Signal processing complete: {success_count}/{len(signals)} executed")

        return results

    def execute_signal(self, signal: dict) -> dict:
        """Execute a single signal payload."""
        signal_type = signal.get("signal", "HOLD").upper()
        symbol = signal.get("symbol", "")

        if signal_type == "BUY":
            return self.execute_buy(signal)
        if signal_type == "SELL":
            return self.execute_sell(symbol, reason="signal")
        return {"status": "skipped", "symbol": symbol, "reason": "hold_signal"}

    def close_position(self, symbol: str) -> dict:
        """Close an existing position through the executor interface."""
        return self.execute_sell(symbol, reason="manual_close")

    def run_cycle(self, symbols: List[str]) -> dict:
        """
        Run a complete trading cycle:
        1. Check stop losses on existing positions
        2. Generate signals for symbols
        3. Execute trades based on signals

        Args:
            symbols: List of symbols to consider for trading

        Returns:
            Cycle results dict
        """
        logger.info(f"Starting trading cycle for {len(symbols)} symbols")
        cycle_start = datetime.now()

        cycle_results = {
            "timestamp": cycle_start.isoformat(),
            "symbols": symbols,
            "positions_before": len(self._open_positions),
            "stop_losses_triggered": [],
            "signals_generated": [],
            "executions": [],
            "positions_after": 0,
            "errors": [],
        }

        try:
            self._refresh_positions()
            cycle_results["positions_before"] = len(self._open_positions)

            stop_loss_positions = self.check_all_stop_losses()
            for sl_pos in stop_loss_positions:
                try:
                    result = self.execute_sell(sl_pos["symbol"], reason="stop_loss")
                    cycle_results["stop_losses_triggered"].append(result)
                except Exception as e:
                    logger.error(f"Failed to execute stop loss for {sl_pos['symbol']}: {e}")
                    cycle_results["errors"].append(f"stop_loss_error_{sl_pos['symbol']}")

        except Exception as e:
            logger.error(f"Error checking stop losses: {e}")
            cycle_results["errors"].append(f"stop_loss_check_error: {e}")

        if self.signals:
            try:
                signals = self.signals.get_signals(symbols, min_confidence=self.min_confidence)
                cycle_results["signals_generated"] = signals
                logger.info(f"Generated {len(signals)} signals")

                if signals:
                    executions = self.process_signals(signals)
                    cycle_results["executions"] = executions

            except Exception as e:
                logger.error(f"Error generating/processing signals: {e}")
                cycle_results["errors"].append(f"signal_error: {e}")
        else:
            logger.warning("No signals module configured, skipping signal generation")

        try:
            self._refresh_positions()
            cycle_results["positions_after"] = len(self._open_positions)
        except Exception as e:
            logger.error(f"Error refreshing positions: {e}")
            cycle_results["errors"].append(f"position_refresh_error: {e}")

        cycle_end = datetime.now()
        cycle_duration = (cycle_end - cycle_start).total_seconds()
        cycle_results["duration_seconds"] = cycle_duration

        logger.info(
            f"Trading cycle complete: {cycle_results['positions_before']} -> "
            f"{cycle_results['positions_after']} positions, "
            f"{len(cycle_results['stop_losses_triggered'])} stop losses, "
            f"{len(cycle_results['executions'])} executions, "
            f"duration={cycle_duration:.2f}s"
        )

        return cycle_results

    def get_order_history(self) -> List[dict]:
        """Get order execution history."""
        return self._order_history.copy()

    def get_performance_stats(self) -> dict:
        """Get performance statistics."""
        self._refresh_positions()

        try:
            account = self.broker.get_account()
            portfolio_value = float(account["portfolio_value"])
            cash = float(account["cash"])
            equity = float(account["equity"])

            closed_trades = [o for o in self._order_history if o.get("side") == "sell"]
            total_pnl = sum(o.get("pnl", 0) for o in closed_trades)

            winning_trades = [o for o in closed_trades if o.get("pnl", 0) > 0]
            losing_trades = [o for o in closed_trades if o.get("pnl", 0) <= 0]

            win_rate = len(winning_trades) / len(closed_trades) if closed_trades else 0

            return {
                "portfolio_value": portfolio_value,
                "cash": cash,
                "equity": equity,
                "open_positions": len(self._open_positions),
                "max_positions": self.max_positions,
                "total_orders": len(self._order_history),
                "closed_trades": len(closed_trades),
                "winning_trades": len(winning_trades),
                "losing_trades": len(losing_trades),
                "win_rate": win_rate,
                "total_pnl": total_pnl,
            }

        except Exception as e:
            logger.error(f"Failed to get performance stats: {e}")
            return {"error": str(e)}


def create_executor(
    broker,
    signals=None,
    max_positions: int = 10,
    max_position_pct: float = 0.02,
    stop_loss_pct: float = 0.15,
    max_total_risk: float = 0.25,
    min_confidence: float = 0.6,
) -> TradingExecutor:
    """
    Factory function to create a TradingExecutor instance.

    Args:
        broker: AlpacaBroker instance
        signals: TradingSignals instance (optional)
        max_positions: Maximum concurrent positions
        max_position_pct: Max position size as % of portfolio
        stop_loss_pct: Stop loss percentage
        max_total_risk: Maximum total risk exposure
        min_confidence: Minimum signal confidence

    Returns:
        TradingExecutor instance
    """
    return TradingExecutor(
        broker=broker,
        signals=signals,
        max_positions=max_positions,
        max_position_pct=max_position_pct,
        stop_loss_pct=stop_loss_pct,
        max_total_risk=max_total_risk,
        min_confidence=min_confidence,
    )


if __name__ == "__main__":
    from broker import AlpacaBroker
    from signals import TradingSignals

    print("=== Trading Executor Demo ===")

    broker = AlpacaBroker(paper=True)
    signals = TradingSignals()
    signals.load_model()

    executor = create_executor(
        broker=broker,
        signals=signals,
        max_positions=10,
        max_position_pct=0.02,
        stop_loss_pct=0.15,
        max_total_risk=0.25,
        min_confidence=0.6,
    )

    print("\n--- Account Info ---")
    account = broker.get_account()
    print(f"Portfolio Value: ${account['portfolio_value']:.2f}")
    print(f"Buying Power: ${account['buying_power']:.2f}")

    print("\n--- Can Trade Check ---")
    can_trade, reason = executor.can_trade("AAPL")
    print(f"AAPL can_trade: {can_trade}, reason: {reason}")

    print("\n--- Run Trading Cycle ---")
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
    results = executor.run_cycle(symbols)

    print(f"Positions before: {results['positions_before']}")
    print(f"Positions after: {results['positions_after']}")
    print(f"Stop losses triggered: {len(results['stop_losses_triggered'])}")
    print(f"Executions: {len(results['executions'])}")

    print("\n--- Performance Stats ---")
    stats = executor.get_performance_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
