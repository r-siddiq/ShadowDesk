"""Stock data pipeline for ML training."""

import random
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

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
    "stock_data_pipeline",
    default_args=default_args,
    description="Stock data ETL pipeline",
    schedule="0 * * * *",
    catchup=False,
) as dag:

    def fetch_stock_data(**context):
        """Simulate fetching stock data from external source"""
        stocks = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
        data = []
        for stock in stocks:
            data.append(
                {
                    "symbol": stock,
                    "price": round(random.uniform(100, 500), 2),
                    "volume": random.randint(1000000, 10000000),
                    "timestamp": datetime.now().isoformat(),
                }
            )

        import json

        data_str = json.dumps(data, indent=2)

        # Save to local file (MinIO upload requires AWS provider)
        import os

        os.makedirs("/airflow", exist_ok=True)
        key = f"raw/stocks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(f'/airflow/{key.replace("/", "_")}', "w") as f:
            f.write(data_str)

        print(f"Saved stock data: {data}")
        return data

    def process_stock_data(**context):
        """Process and transform stock data"""
        ti = context["ti"]
        data = ti.xcom_pull(task_ids="fetch_stock_data")

        processed = []
        for item in data:
            processed.append(
                {
                    **item,
                    "processed": True,
                    "moving_avg": round(item["price"] * 0.98, 2),
                }
            )

        import json

        key = f"processed/stocks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(f'/airflow/{key.replace("/", "_")}', "w") as f:
            json.dump(processed, f)

        print(f"Processed {len(processed)} records")
        return processed

    def generate_embeddings(**context):
        """Generate embeddings for stock data"""
        import json

        stocks = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
        embeddings = []

        for stock in stocks:
            embedding = [random.random() for _ in range(384)]
            embeddings.append({"symbol": stock, "embedding": embedding})

        with open("/airflow/embeddings.json", "w") as f:
            json.dump(embeddings, f)

        print(f"Generated embeddings for {len(embeddings)} stocks")
        return embeddings

    # Task definitions
    fetch_data = PythonOperator(
        task_id="fetch_stock_data",
        python_callable=fetch_stock_data,
    )

    process_data = PythonOperator(
        task_id="process_stock_data",
        python_callable=process_stock_data,
    )

    generate_emb = PythonOperator(
        task_id="generate_embeddings",
        python_callable=generate_embeddings,
    )

    # Task dependencies
    fetch_data >> process_data >> generate_emb
