"""Prediction routes"""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class StockRequest(BaseModel):
    stock: str
    period: Optional[int] = 30


class StockPrediction(BaseModel):
    stock: str
    recommendation: str
    confidence: str
    current_price: Optional[float] = None
    indicators: Optional[dict] = None
    model_version: str = "2.0.0"
    timestamp: Optional[str] = None


@router.get("/{stock}", response_model=StockPrediction)
async def predict_stock(stock: str, period: int = 30):
    """Get stock prediction"""
    from ..services.predictor import predict_stock

    return predict_stock(stock, period)


@router.post("/", response_model=StockPrediction)
async def predict_stock_post(request: StockRequest):
    """Get stock prediction (POST)"""
    from ..services.predictor import predict_stock

    return predict_stock(request.stock, request.period or 30)


@router.get("/")
async def list_supported_stocks():
    """List supported stock symbols"""
    return {
        "symbols": [
            "AAPL",
            "GOOGL",
            "MSFT",
            "AMZN",
            "TSLA",
            "META",
            "NVDA",
            "AMD",
            "NFLX",
            "DIS",
        ],
        "note": "Add more symbols as needed",
    }
