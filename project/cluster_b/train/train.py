"""
Training Pipeline
Train stock prediction model using data from MinIO
"""

import json
import pickle
from io import BytesIO

import numpy as np
import pandas as pd

try:
    from minio import Minio
except ImportError:
    Minio = None

try:
    import mlflow
    import mlflow.sklearn
except ImportError:
    mlflow = None

try:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import accuracy_score
    from sklearn.model_selection import train_test_split
except ImportError:
    sklearn = None


class StockModelTrainer:
    """Train stock prediction model"""

    def __init__(
        self,
        minio_endpoint: str = "localhost:9000",
        access_key: str = "",
        secret_key: str = "",
        mlflow_uri: str = "http://localhost:30368",
    ):

        self.minio_endpoint = minio_endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.mlflow_uri = mlflow_uri
        self.bucket_name = "stock-data"

        self.feature_columns = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
            "SMA_5",
            "SMA_10",
            "SMA_20",
            "SMA_50",
            "EMA_12",
            "EMA_26",
            "RSI",
            "MACD",
            "Signal_Line",
            "MACD_Histogram",
            "BB_Upper",
            "BB_Lower",
            "BB_Width",
            "BB_Position",
            "Volatility_5",
            "Volatility_10",
            "Volatility_20",
        ]

    def _get_minio_client(self):
        if Minio is None:
            return None
        return Minio(self.minio_endpoint, access_key=self.access_key, secret_key=self.secret_key)

    def load_training_data(self) -> pd.DataFrame:
        """Load training data from MinIO"""
        client = self._get_minio_client()

        if client is None:
            return self._create_mock_data()

        try:
            # Get latest raw data
            objects = client.list_objects(self.bucket_name, prefix="raw/")
            latest = sorted(objects, key=lambda x: x.last_modified, reverse=True)

            if latest:
                response = client.get_object(self.bucket_name, latest[0].object_name)
                data = response.read().decode("utf-8")
                df = pd.read_json(data, orient="records")
                return df
        except Exception as e:
            print(f"Error loading data: {e}")

        return self._create_mock_data()

    def _create_mock_data(self) -> pd.DataFrame:
        """Create mock training data"""
        np.random.seed(42)
        n = 500

        return pd.DataFrame(
            {
                "symbol": np.random.choice(["AAPL", "GOOGL", "MSFT"], n),
                "Open": 100 + np.random.randn(n).cumsum(),
                "High": 105 + np.random.randn(n).cumsum(),
                "Low": 95 + np.random.randn(n).cumsum(),
                "Close": 100 + np.random.randn(n).cumsum(),
                "Volume": np.random.randint(1000000, 10000000, n),
                "SMA_5": 100 + np.random.randn(n).cumsum(),
                "SMA_10": 100 + np.random.randn(n).cumsum(),
                "SMA_20": 100 + np.random.randn(n).cumsum(),
                "SMA_50": 100 + np.random.randn(n).cumsum(),
                "EMA_12": 100 + np.random.randn(n).cumsum(),
                "EMA_26": 100 + np.random.randn(n).cumsum(),
                "RSI": np.random.uniform(20, 80, n),
                "MACD": np.random.randn(n),
                "Signal_Line": np.random.randn(n),
                "MACD_Histogram": np.random.randn(n),
                "BB_Upper": 110 + np.random.randn(n).cumsum(),
                "BB_Lower": 90 + np.random.randn(n).cumsum(),
                "BB_Width": np.random.uniform(0.02, 0.1, n),
                "BB_Position": np.random.uniform(0, 1, n),
                "Volatility_5": np.random.uniform(0.1, 0.3, n),
                "Volatility_10": np.random.uniform(0.1, 0.3, n),
                "Volatility_20": np.random.uniform(0.1, 0.3, n),
                "Target": np.random.choice([0, 1], n),
            }
        )

    def add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add computed features to data"""
        # Add price changes
        df["Price_Change"] = df["Close"].diff()
        df["Price_Change_Pct"] = df["Close"].pct_change()

        # Volume features
        df["Volume_Change"] = df["Volume"].pct_change()

        # Fill NaN
        df = df.fillna(0)

        return df

    def train(self) -> dict:
        """Train the model"""
        # Load data
        df = self.load_training_data()
        df = self.add_features(df)

        # Prepare features
        available_features = [f for f in self.feature_columns if f in df.columns]
        X = df[available_features]
        y = df["Target"]

        # Split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Train model
        if sklearn is None:
            return {"status": "sklearn not installed"}

        model = GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42)
        model.fit(X_train, y_train)

        # Evaluate
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        # Save model to MinIO
        client = self._get_minio_client()
        if client:
            try:
                model_bytes = pickle.dumps(model)
                client.put_object(
                    self.bucket_name,
                    "models/stock_model.pkl",
                    BytesIO(model_bytes),
                    length=len(model_bytes),
                )
                print("Model saved to MinIO")
            except Exception as e:
                print(f"Error saving model: {e}")

        # Log to MLflow
        if mlflow:
            try:
                mlflow.set_tracking_uri(self.mlflow_uri)
                with mlflow.start_run():
                    mlflow.log_param("n_estimators", 100)
                    mlflow.log_param("max_depth", 5)
                    mlflow.log_metric("accuracy", accuracy)
                    mlflow.sklearn.log_model(model, "model")
            except Exception as e:
                print(f"MLflow logging error: {e}")

        return {
            "status": "success",
            "accuracy": accuracy,
            "features": available_features,
            "model_type": "GradientBoosting",
        }


def main():
    """Run training"""
    trainer = StockModelTrainer()
    result = trainer.train()
    print("\nTraining Result:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
