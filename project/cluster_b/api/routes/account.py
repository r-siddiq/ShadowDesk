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


class AccountInfo(BaseModel):
    id: str
    account_number: str
    status: str
    currency: str
    cash: float
    portfolio_value: float
    buying_power: float
    pattern_day_trader: bool
    trading_blocked: bool
    transfers_blocked: bool


class PositionInfo(BaseModel):
    symbol: str
    qty: float
    avg_entry_price: float
    market_value: float
    cost_basis: float
    unrealized_pl: float
    unrealized_plpc: float
    current_price: float


class PortfolioResponse(BaseModel):
    total_value: float
    cash: float
    positions: List[PositionInfo]
    portfolio_value: float


class TradeHistoryItem(BaseModel):
    id: str
    symbol: str
    side: str
    qty: float
    filled_avg_price: float
    status: str
    submitted_at: str
    filled_at: Optional[str] = None


@router.get("/", response_model=AccountInfo)
async def get_account(request: Request):
    """Get account info."""
    try:
        broker = get_broker(request)
        account = broker.get_account()
        return AccountInfo(
            id=account.get("id", ""),
            account_number=account.get("account_number", ""),
            status=account.get("status", ""),
            currency=account.get("currency", "USD"),
            cash=float(account.get("cash", 0)),
            portfolio_value=float(account.get("portfolio_value", 0)),
            buying_power=float(account.get("buying_power", 0)),
            pattern_day_trader=account.get("pattern_day_trader", False),
            trading_blocked=account.get("trading_blocked", False),
            transfers_blocked=account.get("transfers_blocked", False),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error fetching account")
        raise HTTPException(status_code=500, detail=f"Error fetching account: {str(e)}")


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(request: Request):
    """Get portfolio summary."""
    try:
        broker = get_broker(request)
        account = broker.get_account()
        positions = broker.get_positions()

        portfolio_value = float(account.get("portfolio_value", 0))
        cash = float(account.get("cash", 0))

        position_list = []
        for pos in positions:
            position_list.append(
                PositionInfo(
                    symbol=pos.get("symbol", ""),
                    qty=float(pos.get("qty", 0)),
                    avg_entry_price=float(pos.get("avg_entry_price", 0)),
                    market_value=float(pos.get("market_value", 0)),
                    cost_basis=float(pos.get("cost_basis", 0)),
                    unrealized_pl=float(pos.get("unrealized_pl", 0)),
                    unrealized_plpc=float(pos.get("unrealized_plpc", 0)),
                    current_price=float(pos.get("current_price", 0)),
                )
            )

        return PortfolioResponse(
            total_value=portfolio_value,
            cash=cash,
            positions=position_list,
            portfolio_value=portfolio_value,
        )
    except Exception as e:
        logger.exception("Error fetching portfolio")
        raise HTTPException(status_code=500, detail=f"Error fetching portfolio: {str(e)}")


@router.get("/history", response_model=List[TradeHistoryItem])
async def get_trade_history(request: Request, limit: int = 50):
    """Get trade history."""
    try:
        broker = get_broker(request)
        trades = broker.get_filled_orders(limit=limit)

        results = []
        for trade in trades:
            results.append(
                TradeHistoryItem(
                    id=trade.get("id", ""),
                    symbol=trade.get("symbol", ""),
                    side=trade.get("side", ""),
                    qty=float(trade.get("qty", 0)),
                    filled_avg_price=float(trade.get("filled_avg_price", 0)),
                    status=trade.get("status", ""),
                    submitted_at=trade.get("submitted_at", ""),
                    filled_at=trade.get("filled_at"),
                )
            )

        return results
    except Exception as e:
        logger.exception("Error fetching trade history")
        raise HTTPException(status_code=500, detail=f"Error fetching trade history: {str(e)}")
