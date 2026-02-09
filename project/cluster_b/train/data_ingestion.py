"""
Data Ingestion Module
Fetches stock data using yfinance and stores in MinIO
"""

import json
from datetime import datetime
from io import BytesIO
from typing import List, Optional

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    print("yfinance not installed. Run: pip install yfinance")

try:
    from minio import Minio
except ImportError:
    print("minio not installed. Run: pip install minio")


class StockDataIngestion:
    """Fetch and store stock market data"""

    def __init__(
        self,
        minio_endpoint: str = "localhost:9000",
        access_key: str = "",
        secret_key: str = "",
        bucket_name: str = "stock-data",
    ):
        self.minio_client = Minio(minio_endpoint, access_key=access_key, secret_key=secret_key)
        self.bucket_name = bucket_name
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Create bucket if it doesn't exist"""
        if not self.minio_client.bucket_exists(self.bucket_name):
            self.minio_client.make_bucket(self.bucket_name)
            print(f"Created bucket: {self.bucket_name}")

    def fetch_stock_data(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        """Fetch stock data from yfinance"""
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)
        df.reset_index(inplace=True)
        df["symbol"] = symbol
        return df

    def fetch_multiple_stocks(self, symbols: List[str], period: str = "1y") -> pd.DataFrame:
        """Fetch data for multiple stocks"""
        all_data = []
        for symbol in symbols:
            try:
                df = self.fetch_stock_data(symbol, period)
                all_data.append(df)
                print(f"Fetched {symbol}: {len(df)} records")
            except Exception as e:
                print(f"Error fetching {symbol}: {e}")

        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame()

    def save_to_minio(self, df: pd.DataFrame, object_name: str) -> bool:
        """Save DataFrame to MinIO as JSON"""
        try:
            json_str = df.to_json(orient="records", date_format="iso")
            data_bytes = json_str.encode("utf-8")

            self.minio_client.put_object(
                self.bucket_name,
                object_name,
                BytesIO(data_bytes),
                length=len(data_bytes),
                content_type="application/json",
            )
            print(f"Saved to MinIO: {self.bucket_name}/{object_name}")
            return True
        except Exception as e:
            print(f"Error saving to MinIO: {e}")
            return False

    def load_from_minio(self, object_name: str) -> Optional[pd.DataFrame]:
        """Load DataFrame from MinIO"""
        try:
            response = self.minio_client.get_object(self.bucket_name, object_name)
            data = response.read().decode("utf-8")
            df = pd.read_json(data, orient="records")
            return df
        except Exception as e:
            print(f"Error loading from MinIO: {e}")
            return None

    def save_raw_data(self, symbols: List[str], period: str = "1y") -> dict:
        """Fetch and save raw stock data"""
        df = self.fetch_multiple_stocks(symbols, period)

        if df.empty:
            return {"status": "error", "message": "No data fetched"}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        object_name = f"raw/stocks_{timestamp}.json"

        success = self.save_to_minio(df, object_name)

        return {
            "status": "success" if success else "error",
            "symbols": symbols,
            "records": len(df),
            "object_name": object_name,
        }


def main():
    """Main function to run data ingestion"""
    ingestion = StockDataIngestion()

    # Default symbols
    symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]

    print(f"Fetching data for: {symbols}")
    result = ingestion.save_raw_data(symbols, period="1y")

    print("\nResult:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
