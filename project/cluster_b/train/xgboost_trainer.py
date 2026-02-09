"""
XGBoost Stock Trainer
Train XGBoost classifier on hourly stock data with technical indicators
"""

import json
import logging
from datetime import datetime
from io import BytesIO
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from xgboost import XGBClassifier
except ImportError:
    print("xgboost not installed. Run: pip install xgboost")

try:
    from minio import Minio
except ImportError:
    print("minio not installed. Run: pip install minio")

try:
    import mlflow
    import mlflow.xgboost
except ImportError:
    print("mlflow not installed. Run: pip install mlflow")

try:
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        precision_score,
        recall_score,
    )
    from sklearn.model_selection import train_test_split
except ImportError:
    print("sklearn not installed. Run: pip install scikit-learn")

try:
    import pyarrow as pa
except ImportError:
    print("pyarrow not installed. Run: pip install pyarrow")

from features import FeatureEngineer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class XGBoostStockTrainer:
    """Train XGBoost classifier for stock direction prediction"""

    def __init__(
        self,
        minio_endpoint: str = "localhost:9000",
        mlflow_uri: str = "http://localhost:30368",
        access_key: str = "",
        secret_key: str = "",
        bucket_name: str = "stock-data",
    ):
        self.minio_endpoint = minio_endpoint
        self.mlflow_uri = mlflow_uri
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name

        self.feature_engineer = FeatureEngineer()

        self.hyperparams = {
            "n_estimators": 100,
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 1,
            "gamma": 0,
            "reg_alpha": 0,
            "reg_lambda": 1,
            "random_state": 42,
            "eval_metric": "logloss",
            "use_label_encoder": False,
        }

        logger.info("XGBoostStockTrainer initialized")
        logger.info(f"MinIO endpoint: {minio_endpoint}")
        logger.info(f"MLflow URI: {mlflow_uri}")

    def _get_minio_client(self) -> Optional[Minio]:
        try:
            return Minio(
                self.minio_endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
            )
        except Exception as e:
            logger.error(f"Error creating MinIO client: {e}")
            return None

    def load_hourly_data(self, symbols: List[str] = None) -> pd.DataFrame:
        """Load hourly stock data from MinIO"""
        client = self._get_minio_client()

        if client is None:
            logger.warning("MinIO client not available, using mock data")
            return self._create_mock_data(symbols)

        all_data = []

        try:
            if symbols is None:
                symbols = self._get_available_symbols(client)

            logger.info(f"Loading hourly data for {len(symbols)} symbols")

            for symbol in symbols:
                try:
                    prefix = f"raw/equities/sp500/{symbol}/"
                    objects = list(client.list_objects(self.bucket_name, prefix=prefix, recursive=True))

                    if not objects:
                        logger.warning(f"No data found for {symbol}")
                        continue

                    latest_objects = sorted(objects, key=lambda x: x.last_modified, reverse=True)[:5]

                    for obj in latest_objects:
                        try:
                            response = client.get_object(self.bucket_name, obj.object_name)
                            data = response.read()

                            buffer = BytesIO(data)
                            table = pa.ipc.open_file(buffer).read_all()
                            df = table.to_pandas()

                            if not df.empty:
                                all_data.append(df)
                                logger.debug(f"Loaded {len(df)} records for {symbol}")

                        except Exception as e:
                            logger.warning(f"Error loading {obj.object_name}: {e}")

                except Exception as e:
                    logger.warning(f"Error processing {symbol}: {e}")

            if all_data:
                combined_df = pd.concat(all_data, ignore_index=True)
                logger.info(f"Loaded total {len(combined_df)} hourly records")
                return combined_df
            else:
                logger.warning("No data loaded from MinIO, using mock data")
                return self._create_mock_data(symbols)

        except Exception as e:
            logger.error(f"Error loading hourly data: {e}")
            return self._create_mock_data(symbols)

    def _get_available_symbols(self, client: Minio) -> List[str]:
        """Get list of available symbols in MinIO"""
        try:
            prefix = "raw/equities/sp500/"
            objects = client.list_objects(self.bucket_name, prefix=prefix, recursive=True)

            symbols = set()
            for obj in objects:
                parts = obj.object_name.split("/")
                if len(parts) >= 4:
                    symbols.add(parts[2])

            return sorted(symbols) if symbols else ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

        except Exception as e:
            logger.error(f"Error getting available symbols: {e}")
            return ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

    def _create_mock_data(self, symbols: List[str] = None) -> pd.DataFrame:
        """Create mock hourly data for testing"""
        if symbols is None:
            symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

        np.random.seed(42)
        all_data = []

        for symbol in symbols:
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

            all_data.append(df)

        logger.info(f"Created mock data: {len(all_data)} symbols, {sum(len(d) for d in all_data)} records")
        return pd.concat(all_data, ignore_index=True)

    def prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray, List[str]]:
        """Prepare features using FeatureEngineer"""
        logger.info("Creating features with FeatureEngineer")

        if "datetime" in df.columns:
            df = df.sort_values(["symbol", "datetime"]).reset_index(drop=True)
        elif "Date" in df.columns:
            df = df.rename(columns={"Date": "datetime"})
            df = df.sort_values(["symbol", "datetime"]).reset_index(drop=True)

        df_features = self.feature_engineer.create_features(df, add_target=True)

        feature_cols = self.feature_engineer.get_feature_columns()
        available_features = [f for f in feature_cols if f in df_features.columns]

        logger.info(f"Using {len(available_features)} features")

        X = df_features[available_features].values
        y = df_features["Target"].values

        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        return df_features, X, y, available_features

    def train(self, symbols: List[str] = None) -> dict:
        """Train XGBoost classifier"""
        logger.info("Starting XGBoost training pipeline")

        df = self.load_hourly_data(symbols)

        if df.empty:
            logger.error("No data available for training")
            return {"status": "error", "message": "No data available"}

        df_features, X, y, feature_cols = self.prepare_features(df)

        logger.info(f"Training data shape: X={X.shape}, y={y.shape}")
        logger.info(f"Target distribution: UP={sum(y)}, DOWN={len(y) - sum(y)}")

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)

        logger.info(f"Train size: {len(X_train)}, Test size: {len(X_test)}")

        model = XGBClassifier(**self.hyperparams)

        logger.info("Training XGBoost model...")
        model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

        y_pred = model.predict(X_test)

        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1": f1_score(y_test, y_pred, zero_division=0),
        }

        logger.info(f"Metrics: {metrics}")

        self._log_to_mlflow(model, metrics, feature_cols, X_train, y_train)

        save_success = self.save_model(model)

        feature_importance = dict(zip(feature_cols, model.feature_importances_.tolist()))

        result = {
            "status": "success",
            "metrics": metrics,
            "feature_count": len(feature_cols),
            "train_size": len(X_train),
            "test_size": len(X_test),
            "model_saved": save_success,
            "hyperparams": self.hyperparams,
            "top_features": sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10],
        }

        logger.info(f"Training complete: {result['status']}, Accuracy: {metrics['accuracy']:.4f}")

        return result

    def _log_to_mlflow(
        self,
        model,
        metrics: dict,
        feature_cols: List[str],
        X_train: np.ndarray,
        y_train: np.ndarray,
    ):
        """Log training results to MLflow"""
        try:
            mlflow.set_tracking_uri(self.mlflow_uri)

            with mlflow.start_run(run_name="xgboost_stock_direction"):
                for param_name, param_value in self.hyperparams.items():
                    mlflow.log_param(param_name, param_value)

                for metric_name, metric_value in metrics.items():
                    mlflow.log_metric(metric_name, metric_value)

                mlflow.log_param("n_features", len(feature_cols))
                mlflow.log_param("train_samples", len(X_train))
                mlflow.log_param("target", "Next hour direction (UP/DOWN)")

                mlflow.xgboost.log_model(
                    model,
                    artifact_path="model",
                    registered_model_name="xgboost_stock_model",
                )

                feature_importance = dict(zip(feature_cols, model.feature_importances_.tolist()))
                top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]

                mlflow.log_dict({"top_features": top_features}, "feature_importance.json")

            logger.info("Logged to MLflow successfully")

        except Exception as e:
            logger.error(f"Error logging to MLflow: {e}")

    def save_model(self, model) -> bool:
        """Save trained model to MinIO"""
        client = self._get_minio_client()

        if client is None:
            logger.warning("MinIO client not available, cannot save model")
            return False

        try:
            model_json = model.get_booster().get_dump(with_stats=False)

            model_data = {
                "model_type": "XGBoost",
                "hyperparams": self.hyperparams,
                "model_json": model_json,
                "saved_at": datetime.now().isoformat(),
            }

            json_str = json.dumps(model_data)
            model_bytes = json_str.encode("utf-8")

            object_name = "models/xgboost_stock_model.json"

            client.put_object(
                self.bucket_name,
                object_name,
                BytesIO(model_bytes),
                length=len(model_bytes),
                content_type="application/json",
            )

            logger.info(f"Model saved to MinIO: {object_name}")
            return True

        except Exception as e:
            logger.error(f"Error saving model to MinIO: {e}")
            return False


def main():
    """Main function to run XGBoost training"""
    trainer = XGBoostStockTrainer()

    symbols = [
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "TSLA",
        "META",
        "NVDA",
        "JPM",
        "V",
        "WMT",
    ]

    logger.info(f"Starting training for {len(symbols)} symbols")

    result = trainer.train(symbols=symbols)

    print("\n" + "=" * 50)
    print("TRAINING RESULT")
    print("=" * 50)
    print(json.dumps(result, indent=2, default=str))
    print("=" * 50)

    return result


if __name__ == "__main__":
    main()
