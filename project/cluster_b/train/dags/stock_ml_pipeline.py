"""
Stock Pipeline DAG
Automated ML pipeline for stock prediction
"""

import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Add project to path
sys.path.insert(0, "/opt/airflow/project")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2026, 2, 16),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "stock_ml_pipeline",
    default_args=default_args,
    description="Stock data fetching and ML training pipeline",
    schedule="0 0 * * *",  # Daily at midnight
    catchup=False,
) as dag:

    def fetch_stock_data(**context):
        """Fetch stock data from yfinance and save to MinIO"""
        try:
            from cluster_b.train.data_ingestion import StockDataIngestion

            ingestion = StockDataIngestion(
                minio_endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
                access_key=os.getenv("MINIO_ACCESS_KEY", ""),
                secret_key=os.getenv("MINIO_SECRET_KEY", ""),
                bucket_name="stock-data",
            )

            symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
            result = ingestion.save_raw_data(symbols, period="1y")

            print(f"Data fetch result: {result}")
            return result
        except Exception as e:
            print(f"Error fetching data: {e}")
            return {"status": "error", "message": str(e)}

    def train_model(**context):
        """Train the stock prediction model"""
        try:
            from cluster_b.train.train import StockModelTrainer

            trainer = StockModelTrainer(
                minio_endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
                access_key=os.getenv("MINIO_ACCESS_KEY", ""),
                secret_key=os.getenv("MINIO_SECRET_KEY", ""),
                mlflow_uri=os.getenv("MLFLOW_TRACKING_URI", "http://localhost:30368"),
            )

            result = trainer.train()

            print(f"Training result: {result}")
            return result
        except Exception as e:
            print(f"Error training model: {e}")
            return {"status": "error", "message": str(e)}

    def create_embeddings(**context):
        """Create embeddings for stock data in Qdrant"""
        try:
            import numpy as np
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            # Connect to Qdrant
            client = QdrantClient(host="localhost", port=6333, check_compatibility=False)

            # Create collection if not exists
            collections = client.get_collections()
            if not any(c.name == "stock_embeddings" for c in collections.collections):
                client.create_collection(
                    collection_name="stock_embeddings",
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                )

            # Generate sample embeddings
            stocks = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
            vectors = []
            for stock in stocks:
                vectors.append(
                    {
                        "id": hash(stock) % 1000000,
                        "vector": np.random.randn(384).tolist(),
                        "payload": {"symbol": stock},
                    }
                )

            client.upsert(collection_name="stock_embeddings", points=vectors)

            print(f"Created embeddings for {len(stocks)} stocks")
            return {"status": "success", "count": len(stocks)}
        except Exception as e:
            print(f"Error creating embeddings: {e}")
            return {"status": "error", "message": str(e)}

    # Task definitions
    fetch_task = PythonOperator(
        task_id="fetch_stock_data",
        python_callable=fetch_stock_data,
    )

    train_task = PythonOperator(
        task_id="train_model",
        python_callable=train_model,
    )

    embeddings_task = PythonOperator(
        task_id="create_embeddings",
        python_callable=create_embeddings,
    )

    # Task dependencies
    fetch_task >> train_task >> embeddings_task
