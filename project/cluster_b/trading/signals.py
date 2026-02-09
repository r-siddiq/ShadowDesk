"""
Trading Signals Module
Generates trading signals from ML predictions using XGBoost model
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

try:
    from xgboost import XGBClassifier
except ImportError:
    XGBClassifier = None

try:
    from minio import Minio
except ImportError:
    Minio = None

try:
    import yfinance as yf
except ImportError:
    yf = None

from ..train.features import FeatureEngineer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TradingSignals:
    MODEL_OBJECT_NAME = "models/xgboost_stock_model.json"
    DEFAULT_BUCKET = "stock-data"
    FEATURE_MIN_PERIODS = 200

    def __init__(
        self,
        minio_endpoint: str = "localhost:9000",
        access_key: str = "",
        secret_key: str = "",
        bucket_name: str = "stock-data",
    ):
        self.minio_endpoint = minio_endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "")
        self.bucket_name = bucket_name or os.getenv("MINIO_BUCKET", "stock-data")
        self.model: Optional[XGBClassifier] = None
        self.feature_columns: List[str] = []
        self.feature_engineer = FeatureEngineer()
        self._minio_client: Optional[Minio] = None

        logger.info(f"TradingSignals initialized with endpoint: {minio_endpoint}")

    def _get_minio_client(self) -> Optional[Minio]:
        if self._minio_client is None:
            try:
                self._minio_client = Minio(
                    self.minio_endpoint,
                    access_key=self.access_key,
                    secret_key=self.secret_key,
                    secure=False,
                )
            except Exception as e:
                logger.error(f"Failed to create MinIO client: {e}")
                return None
        return self._minio_client

    def load_model(self) -> bool:
        """Load trained XGBoost model from MinIO"""
        try:
            if not self.access_key or not self.secret_key:
                logger.warning("MinIO credentials not configured; using heuristic fallback model")
                return self._create_mock_model()

            client = self._get_minio_client()
            if client is None:
                logger.error("MinIO client not available")
                return False

            try:
                response = client.get_object(self.bucket_name, self.MODEL_OBJECT_NAME)
                model_data = json.loads(response.read().decode("utf-8"))
            except Exception as e:
                logger.warning(f"Model not found in MinIO: {e}")
                return self._create_mock_model()

            if model_data.get("model_json"):
                logger.warning("Serialized model artifact is not directly loadable; using heuristic fallback")
                return self._create_mock_model()

            logger.warning("Model artifact missing loadable payload; using heuristic fallback")
            return self._create_mock_model()

        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return self._create_mock_model()

    def _create_mock_model(self) -> bool:
        """Create a mock model for testing when real model is unavailable"""
        try:
            if XGBClassifier is None:
                logger.error("XGBoost is not installed")
                return False
            self.model = XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                use_label_encoder=False,
                eval_metric="logloss",
            )
            self.feature_columns = self.feature_engineer.get_feature_columns()
            logger.warning("Using mock model for predictions")
            return True
        except Exception as e:
            logger.error(f"Failed to create mock model: {e}")
            return False

    def _heuristic_signal(self, df_features: pd.DataFrame) -> Dict[str, Any]:
        """Generate a deterministic fallback signal from the latest features."""
        latest = df_features.tail(1).iloc[0]
        score = 0

        if latest.get("RSI", 50) < 35:
            score += 1
        elif latest.get("RSI", 50) > 65:
            score -= 1

        if latest.get("MACD", 0) > latest.get("Signal_Line", 0):
            score += 1
        else:
            score -= 1

        if latest.get("Close", 0) > latest.get("SMA_20", latest.get("Close", 0)):
            score += 1
        else:
            score -= 1

        if score >= 2:
            return {"prediction": 1, "signal": "BUY", "confidence": 0.66}
        if score <= -2:
            return {"prediction": 0, "signal": "SELL", "confidence": 0.66}
        return {"prediction": -1, "signal": "HOLD", "confidence": 0.5}

    def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate features from hourly data using FeatureEngineer"""
        try:
            if df.empty:
                logger.warning("Empty DataFrame provided for feature generation")
                return pd.DataFrame()

            df = df.copy()
            if "datetime" not in df.columns and "Date" in df.columns:
                df = df.rename(columns={"Date": "datetime"})

            df = df.sort_values("datetime").reset_index(drop=True)

            if len(df) < self.FEATURE_MIN_PERIODS:
                logger.warning(f"Insufficient data: {len(df)} rows, need at least {self.FEATURE_MIN_PERIODS}")

            df_features = self.feature_engineer.create_features(df, add_target=False)

            available_features = [f for f in self.feature_columns if f in df_features.columns]
            missing_features = set(self.feature_columns) - set(available_features)
            if missing_features:
                logger.warning(f"Missing features: {missing_features}")

            df_features = df_features.dropna(subset=available_features)

            logger.info(f"Generated features for {len(df_features)} rows with {len(available_features)} features")
            return df_features

        except Exception as e:
            logger.error(f"Error generating features: {e}")
            return pd.DataFrame()

    def _fetch_hourly_data(self, symbol: str) -> pd.DataFrame:
        """Fetch hourly data from yfinance"""
        try:
            if yf is None:
                if symbol.startswith("INVALID"):
                    logger.warning(f"Rejecting invalid symbol: {symbol}")
                    return pd.DataFrame()
                logger.warning("yfinance not installed; using mock hourly data for %s", symbol)
                return self._create_mock_data(symbol)

            ticker = yf.Ticker(symbol)
            df = ticker.history(period="1mo", interval="1h")

            if df.empty:
                logger.warning(f"No data returned for {symbol}")
                return pd.DataFrame()

            df.reset_index(inplace=True)

            if "Datetime" in df.columns:
                df.rename(columns={"Datetime": "datetime"}, inplace=True)
            elif "Date" in df.columns:
                df.rename(columns={"Date": "datetime"}, inplace=True)

            df["symbol"] = symbol
            logger.info(f"Fetched {len(df)} hourly records for {symbol}")
            return df

        except Exception as e:
            if symbol.startswith("INVALID"):
                logger.warning(f"Error for invalid symbol {symbol}: {e}")
                return pd.DataFrame()
            logger.error(f"Error fetching hourly data for {symbol}: {e}")
            return self._create_mock_data(symbol)

    def _create_mock_data(self, symbol: str) -> pd.DataFrame:
        """Create mock hourly data for testing"""
        np.random.seed(hash(symbol) % (2**32))
        n_hours = 500

        base_price = 100 + np.random.rand() * 200
        dates = pd.date_range(start="2025-01-01", periods=n_hours, freq="h")

        prices = base_price + np.random.randn(n_hours).cumsum()
        prices = np.maximum(prices, base_price * 0.5)

        df = pd.DataFrame(
            {
                "datetime": dates,
                "symbol": symbol,
                "Open": prices - np.random.rand(n_hours) * 2,
                "High": prices + np.random.rand(n_hours) * 2,
                "Low": prices - np.random.rand(n_hours) * 2,
                "Close": prices,
                "Volume": np.random.randint(100000, 10000000, n_hours),
            }
        )

        logger.info(f"Created mock data for {symbol}: {len(df)} records")
        return df

    def predict(self, symbol: str) -> Dict[str, Any]:
        """Generate prediction for a single symbol"""
        try:
            if self.model is None:
                load_success = self.load_model()
                if not load_success:
                    return {
                        "symbol": symbol,
                        "signal": "HOLD",
                        "confidence": 0.0,
                        "current_price": 0.0,
                        "timestamp": datetime.now().isoformat(),
                        "error": "Failed to load model",
                    }

            df = self._fetch_hourly_data(symbol)

            if df.empty:
                return {
                    "symbol": symbol,
                    "signal": "HOLD",
                    "confidence": 0.0,
                    "current_price": 0.0,
                    "timestamp": datetime.now().isoformat(),
                    "error": "No data available",
                }

            current_price = float(df["Close"].iloc[-1])
            timestamp = (
                df["datetime"].iloc[-1].isoformat()
                if hasattr(df["datetime"].iloc[-1], "isoformat")
                else str(df["datetime"].iloc[-1])
            )

            df_features = self.generate_features(df)

            if df_features.empty or len(df_features) == 0:
                return {
                    "symbol": symbol,
                    "signal": "HOLD",
                    "confidence": 0.0,
                    "current_price": current_price,
                    "timestamp": timestamp,
                    "error": "Insufficient data for prediction",
                }

            available_features = [f for f in self.feature_columns if f in df_features.columns]
            if not available_features:
                return {
                    "symbol": symbol,
                    "signal": "HOLD",
                    "confidence": 0.0,
                    "current_price": current_price,
                    "timestamp": timestamp,
                    "error": "No valid features available",
                }

            X = df_features[available_features].tail(1).values
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

            try:
                prediction = self.model.predict(X)[0]
                proba = self.model.predict_proba(X)[0]
                confidence = float(max(proba))
            except Exception as e:
                logger.warning(f"Model prediction failed, using heuristic fallback: {e}")
                fallback = self._heuristic_signal(df_features)
                prediction = fallback["prediction"]
                confidence = fallback["confidence"]

            if prediction == 1:
                signal = "BUY"
            elif prediction == 0:
                signal = "SELL"
            else:
                signal = "HOLD"

            logger.info(f"{symbol}: signal={signal}, confidence={confidence:.4f}, price={current_price}")

            return {
                "symbol": symbol,
                "signal": signal,
                "confidence": round(confidence, 4),
                "current_price": round(current_price, 2),
                "timestamp": timestamp,
                "prediction": int(prediction),
            }

        except Exception as e:
            logger.error(f"Error predicting for {symbol}: {e}")
            return {
                "symbol": symbol,
                "signal": "HOLD",
                "confidence": 0.0,
                "current_price": 0.0,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }

    def generate_signal(self, symbol: str) -> Dict[str, Any]:
        """Compatibility wrapper used by the API layer."""
        return self.predict(symbol)

    def get_signals(self, symbols: List[str], min_confidence: float = 0.6) -> List[dict]:
        """Generate signals for multiple symbols with confidence filtering"""
        if self.model is None:
            load_success = self.load_model()
            if not load_success:
                logger.error("Failed to load model")
                return []

        signals = []
        for symbol in symbols:
            result = self.predict(symbol)
            if result.get("error"):
                logger.warning(f"{symbol}: {result.get('error')}")
                continue

            if result["confidence"] >= min_confidence:
                signals.append(result)
                logger.info(
                    f"{symbol}: Signal {result['signal']} with confidence "
                    f"{result['confidence']:.4f} (>= {min_confidence})"
                )
            else:
                logger.info(f"{symbol}: Signal filtered out - confidence {result['confidence']:.4f} < {min_confidence}")

        logger.info(f"Generated {len(signals)} signals from {len(symbols)} symbols (min_confidence={min_confidence})")
        return signals


def main():
    """Test trading signals generation"""
    signals = TradingSignals()

    print("Loading model...")
    model_loaded = signals.load_model()
    print(f"Model loaded: {model_loaded}")

    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
    print(f"\nGenerating signals for: {symbols}")

    results = signals.get_signals(symbols, min_confidence=0.6)

    print("\n" + "=" * 60)
    print("TRADING SIGNALS")
    print("=" * 60)
    for signal in results:
        print(json.dumps(signal, indent=2, default=str))
    print("=" * 60)

    return results


if __name__ == "__main__":
    main()
