"""
Stock Prediction Model Service
Provides predictions for stock buy recommendations
"""

from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None


class StockPredictor:
    """Stock price prediction and recommendation"""

    def __init__(self):
        # Simple moving average windows
        self.sma_windows = [5, 10, 20, 50]

    def fetch_latest_data(self, symbol: str, period: str = "3mo") -> Optional[pd.DataFrame]:
        """Fetch latest stock data"""
        if yf is None:
            return self._create_mock_data(symbol)

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)
            df.reset_index(inplace=True)
            df["symbol"] = symbol
            return df
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return self._create_mock_data(symbol)

    def _create_mock_data(self, symbol: str) -> pd.DataFrame:
        """Create mock data for testing"""
        dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
        np.random.seed(hash(symbol) % 1000)

        return pd.DataFrame(
            {
                "Date": dates,
                "Open": 100 + np.random.randn(60).cumsum(),
                "High": 105 + np.random.randn(60).cumsum(),
                "Low": 95 + np.random.randn(60).cumsum(),
                "Close": 100 + np.random.randn(60).cumsum(),
                "Volume": np.random.randint(1000000, 10000000, 60),
                "symbol": symbol,
            }
        )

    def calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Calculate technical indicators"""
        if df.empty or "Close" not in df.columns:
            return {}

        close = df["Close"].iloc[-1]

        # Simple Moving Averages
        sma_values = {}
        for window in self.sma_windows:
            if len(df) >= window:
                sma_values[f"SMA_{window}"] = df["Close"].iloc[-window:].mean()

        # RSI
        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_value = rsi.iloc[-1] if not rsi.empty else 50

        # MACD
        exp1 = df["Close"].ewm(span=12, adjust=False).mean()
        exp2 = df["Close"].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()

        # Current price vs SMAs
        current_price = close
        price_vs_sma20 = (current_price - sma_values.get("SMA_20", current_price)) / current_price * 100

        return {
            "current_price": round(current_price, 2),
            "sma_5": round(sma_values.get("SMA_5", current_price), 2),
            "sma_10": round(sma_values.get("SMA_10", current_price), 2),
            "sma_20": round(sma_values.get("SMA_20", current_price), 2),
            "sma_50": round(sma_values.get("SMA_50", current_price), 2),
            "rsi": round(rsi_value, 2) if not pd.isna(rsi_value) else 50,
            "macd": round(macd.iloc[-1], 2) if not macd.empty else 0,
            "macd_signal": round(signal.iloc[-1], 2) if not signal.empty else 0,
            "price_vs_sma20_pct": round(price_vs_sma20, 2),
        }

    def generate_signal(self, indicators: Dict) -> str:
        """Generate buy/sell/hold signal based on indicators"""
        score = 0

        # RSI signals
        rsi = indicators.get("rsi", 50)
        if rsi < 30:
            score += 2  # Oversold - buy signal
        elif rsi > 70:
            score -= 2  # Overbought - sell signal

        # Price vs SMA
        if indicators.get("price_vs_sma20_pct", 0) > 5:
            score += 1  # Above SMA - bullish
        elif indicators.get("price_vs_sma20_pct", 0) < -5:
            score -= 1  # Below SMA - bearish

        # MACD
        if indicators.get("macd", 0) > indicators.get("macd_signal", 0):
            score += 1  # MACD crossover - bullish
        else:
            score -= 1

        # Determine signal
        if score >= 2:
            return "BUY"
        elif score <= -2:
            return "SELL"
        else:
            return "HOLD"

    def predict(self, symbol: str) -> Dict:
        """Generate prediction for a stock symbol"""
        # Fetch data
        df = self.fetch_latest_data(symbol)

        if df is None or df.empty:
            return {"symbol": symbol, "error": "Could not fetch data"}

        # Calculate indicators
        indicators = self.calculate_indicators(df)

        # Generate signal
        signal = self.generate_signal(indicators)

        # Confidence based on RSI
        rsi = indicators.get("rsi", 50)
        if rsi < 30 or rsi > 70:
            confidence = "high"
        elif rsi < 40 or rsi > 60:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "symbol": symbol,
            "signal": signal,
            "confidence": confidence,
            "current_price": indicators.get("current_price"),
            "indicators": indicators,
            "timestamp": datetime.now().isoformat(),
        }

    def predict_batch(self, symbols: List[str]) -> List[Dict]:
        """Generate predictions for multiple symbols"""
        return [self.predict(symbol) for symbol in symbols]


# Singleton instance
_predictor = None


def get_predictor() -> StockPredictor:
    """Get predictor instance"""
    global _predictor
    if _predictor is None:
        _predictor = StockPredictor()
    return _predictor


def predict_stock(stock: str, period: int = 30) -> dict:
    """
    Generate stock prediction.

    Uses technical indicators (SMA, RSI, MACD) for signals.
    """
    predictor = get_predictor()
    result = predictor.predict(stock)

    return {
        "stock": stock.upper(),
        "recommendation": result.get("signal", "HOLD"),
        "confidence": result.get("confidence", "low"),
        "current_price": result.get("current_price"),
        "indicators": result.get("indicators", {}),
        "model_version": "2.0.0",
        "timestamp": result.get("timestamp"),
    }
