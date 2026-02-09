import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


def get_broker(request: Request):
    """Lazy initialization of broker."""
    if not hasattr(request.app.state, "broker") or request.app.state.broker is None:
        from ...trading.broker import AlpacaBroker

        request.app.state.broker = AlpacaBroker()
    return request.app.state.broker


def get_executor(request: Request):
    """Lazy initialization of trading executor."""
    if not hasattr(request.app.state, "executor") or request.app.state.executor is None:
        broker = get_broker(request)
        from ...trading.signals import TradingSignals

        signals = TradingSignals()
        signals.load_model()
        from ...trading.executor import TradingExecutor

        request.app.state.executor = TradingExecutor(broker=broker, signals=signals, min_confidence=0.6)
    return request.app.state.executor


class OrderRequest(BaseModel):
    symbol: str
    qty: int
    side: str
    order_type: str = "market"
    limit_price: Optional[float] = None


class SignalRequest(BaseModel):
    symbols: List[str]
    min_confidence: float = 0.6


class SignalResponse(BaseModel):
    symbol: str
    signal: str
    confidence: float
    current_price: Optional[float] = None
    timestamp: Optional[str] = None
    prediction: Optional[int] = None
    error: Optional[str] = None


class CycleRequest(BaseModel):
    symbols: List[str]


@router.get("/signals/{symbol}", response_model=SignalResponse)
async def get_signal(request: Request, symbol: str):
    """Return trading signal for a symbol."""
    try:
        executor = get_executor(request)
        signal_data = executor.signals.generate_signal(symbol)
        if signal_data is None or signal_data.get("error"):
            error_msg = signal_data.get("error") if signal_data else f"Could not generate signal for {symbol}"
            raise HTTPException(status_code=404, detail=error_msg)
        return SignalResponse(
            symbol=symbol,
            signal=signal_data.get("signal", "HOLD"),
            confidence=signal_data.get("confidence", 0.0),
            current_price=signal_data.get("current_price"),
            timestamp=signal_data.get("timestamp"),
            prediction=signal_data.get("prediction"),
            error=signal_data.get("error"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error generating signal for %s", symbol)
        raise HTTPException(status_code=500, detail=f"Error generating signal: {str(e)}")


@router.post("/signals/batch", response_model=List[SignalResponse])
async def get_signals_batch(request: Request, signal_request: SignalRequest):
    """Return signals for multiple symbols."""
    try:
        executor = get_executor(request)
        signal_payloads = executor.signals.get_signals(
            signal_request.symbols,
            min_confidence=signal_request.min_confidence,
        )
        results = [
            SignalResponse(
                symbol=signal_data.get("symbol", ""),
                signal=signal_data.get("signal", "HOLD"),
                confidence=signal_data.get("confidence", 0.0),
                current_price=signal_data.get("current_price"),
                timestamp=signal_data.get("timestamp"),
                prediction=signal_data.get("prediction"),
                error=signal_data.get("error"),
            )
            for signal_data in signal_payloads
        ]
        return results
    except Exception as e:
        logger.exception("Error generating batch signals")
        raise HTTPException(status_code=500, detail=f"Error generating batch signals: {str(e)}")


@router.post("/orders")
async def submit_order(request: Request, order: OrderRequest):
    """Submit a trading order."""
    try:
        executor = get_executor(request)
        result = executor.broker.submit_order(
            symbol=order.symbol,
            qty=order.qty,
            side=order.side,
            order_type=order.order_type,
            limit_price=order.limit_price,
        )
        return {"status": "success", "order": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error submitting order for %s", order.symbol)
        raise HTTPException(status_code=500, detail=f"Error submitting order: {str(e)}")


@router.get("/orders")
async def get_orders(request: Request):
    """Get pending orders."""
    try:
        broker = get_broker(request)
        orders = broker.get_pending_orders()
        return {"orders": orders, "count": len(orders)}
    except Exception as e:
        logger.exception("Error fetching orders")
        raise HTTPException(status_code=500, detail=f"Error fetching orders: {str(e)}")


@router.delete("/orders/{order_id}")
async def cancel_order(request: Request, order_id: str):
    """Cancel an order."""
    try:
        broker = get_broker(request)
        result = broker.cancel_order(order_id)
        return {"status": "success", "order_id": order_id, "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error canceling order %s", order_id)
        raise HTTPException(status_code=500, detail=f"Error canceling order: {str(e)}")


@router.post("/cycle")
async def run_trading_cycle(request: Request, cycle_request: CycleRequest):
    """Run full trading cycle: check stops, generate signals, execute."""
    try:
        executor = get_executor(request)
        cycle_results = executor.run_cycle(cycle_request.symbols)
        cycle_results["processed"] = len(cycle_request.symbols)
        cycle_results["orders_executed"] = sum(
            1 for execution in cycle_results.get("executions", []) if execution.get("status") == "success"
        )
        return cycle_results
    except Exception as e:
        logger.exception("Error running trading cycle")
        raise HTTPException(status_code=500, detail=f"Error running trading cycle: {str(e)}")


@router.get("/positions")
async def get_positions(request: Request):
    """Get current positions."""
    try:
        executor = get_executor(request)
        positions = executor.get_open_positions()
        return {"positions": list(positions.values()), "count": len(positions)}
    except Exception as e:
        logger.exception("Error fetching positions")
        raise HTTPException(status_code=500, detail=f"Error fetching positions: {str(e)}")


@router.delete("/positions/{symbol}")
async def close_position(request: Request, symbol: str):
    """Close a position."""
    try:
        broker = get_broker(request)
        result = broker.close_position(symbol)
        return {"status": "success", "symbol": symbol, "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error closing position %s", symbol)
        raise HTTPException(status_code=500, detail=f"Error closing position: {str(e)}")
