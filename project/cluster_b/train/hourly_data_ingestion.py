"""
Hourly Stock Data Ingestion Module
Fetches hourly stock data from yfinance and stores in MinIO as Parquet
"""

import logging
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

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    print("pyarrow not installed. Run: pip install pyarrow")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class HourlyStockDataIngestion:
    """Fetch and store hourly stock market data in Parquet format"""

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
        logger.info(f"HourlyStockDataIngestion initialized with bucket: {bucket_name}")

    def _ensure_bucket(self):
        """Create bucket if it doesn't exist"""
        try:
            if not self.minio_client.bucket_exists(self.bucket_name):
                self.minio_client.make_bucket(self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Error ensuring bucket: {e}")

    def fetch_hourly_data(self, symbol: str, period: str = "1mo") -> pd.DataFrame:
        """Fetch hourly stock data from yfinance"""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval="1h")

            if df.empty:
                logger.warning(f"No data returned for {symbol}")
                return df

            df.reset_index(inplace=True)

            if "Datetime" in df.columns:
                df.rename(columns={"Datetime": "datetime"}, inplace=True)
            elif "Date" in df.columns:
                df.rename(columns={"Date": "datetime"}, inplace=True)

            df["symbol"] = symbol
            df["fetched_at"] = datetime.now().isoformat()

            logger.info(f"Fetched {len(df)} hourly records for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching hourly data for {symbol}: {e}")
            return pd.DataFrame()

    def save_to_minio_parquet(self, df: pd.DataFrame, symbol: str) -> bool:
        """Save DataFrame to MinIO as Parquet file"""
        if df.empty:
            logger.warning(f"Empty DataFrame for {symbol}, skipping save")
            return False

        try:
            if "datetime" not in df.columns:
                logger.error("No datetime column found in DataFrame")
                return False

            reference_date = df["datetime"].min()
            year = reference_date.strftime("%Y")
            month = reference_date.strftime("%m")
            day = reference_date.strftime("%d")
            date_str = reference_date.strftime("%Y%m%d")

            object_name = f"raw/equities/sp500/{symbol}/{year}/{month}/{day}/{symbol}_{date_str}.parquet"

            buffer = BytesIO()
            table = pa.Table.from_pandas(df)
            pq.write_table(table, buffer)
            buffer.seek(0)

            self.minio_client.put_object(
                self.bucket_name,
                object_name,
                buffer,
                length=buffer.getbuffer().nbytes,
                content_type="application/octet-stream",
            )

            logger.info(f"Saved {symbol} to MinIO: {object_name}")
            return True

        except Exception as e:
            logger.error(f"Error saving {symbol} to MinIO: {e}")
            return False

    def update_symbol(self, symbol: str, period: str = "1mo") -> dict:
        """Fetch and save latest hourly data for a single symbol"""
        try:
            logger.info(f"Updating hourly data for {symbol}")

            df = self.fetch_hourly_data(symbol, period)

            if df.empty:
                return {
                    "symbol": symbol,
                    "status": "error",
                    "message": "No data fetched",
                    "records": 0,
                }

            success = self.save_to_minio_parquet(df, symbol)

            return {
                "symbol": symbol,
                "status": "success" if success else "error",
                "records": len(df),
                "date_range": {
                    "start": (df["datetime"].min().isoformat() if "datetime" in df.columns else None),
                    "end": (df["datetime"].max().isoformat() if "datetime" in df.columns else None),
                },
            }

        except Exception as e:
            logger.error(f"Error updating symbol {symbol}: {e}")
            return {
                "symbol": symbol,
                "status": "error",
                "message": str(e),
                "records": 0,
            }

    def update_all_symbols(self, symbols: List[str], period: str = "1mo") -> dict:
        """Fetch and save hourly data for multiple symbols"""
        results = []
        success_count = 0
        error_count = 0

        logger.info(f"Starting bulk update for {len(symbols)} symbols")

        for symbol in symbols:
            result = self.update_symbol(symbol, period)
            results.append(result)

            if result["status"] == "success":
                success_count += 1
            else:
                error_count += 1

            logger.info(f"Processed {symbol}: {result['status']}")

        logger.info(f"Bulk update complete. Success: {success_count}, Errors: {error_count}")

        return {
            "status": "completed",
            "total_symbols": len(symbols),
            "success_count": success_count,
            "error_count": error_count,
            "results": results,
        }

    def fetch_latest_hourly_data(self, symbol: str) -> pd.DataFrame:
        """Fetch the most recent hourly data for updating existing data"""
        return self.fetch_hourly_data(symbol, period="5d")

    def get_stored_dates(self, symbol: str) -> List[str]:
        """Get list of dates for which data is already stored"""
        try:
            prefix = f"raw/equities/sp500/{symbol}/"
            objects = self.minio_client.list_objects(self.bucket_name, prefix=prefix, recursive=True)

            dates = []
            for obj in objects:
                parts = obj.object_name.split("/")
                if len(parts) >= 7:
                    date_str = parts[-1].replace(f"{symbol}_", "").replace(".parquet", "")
                    if date_str:
                        dates.append(date_str)

            return sorted(dates)

        except Exception as e:
            logger.error(f"Error getting stored dates for {symbol}: {e}")
            return []

    def get_latest_data_date(self, symbol: str) -> Optional[datetime]:
        """Get the most recent stored date for a symbol"""
        dates = self.get_stored_dates(symbol)
        if dates:
            try:
                return datetime.strptime(dates[-1], "%Y%m%d")
            except Exception as e:
                logger.error(f"Error parsing date: {e}")
        return None


def get_sp500_symbols() -> List[str]:
    """Get list of S&P 500 symbols (common ones)"""
    return [
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "NVDA",
        "META",
        "TSLA",
        "BRK-B",
        "UNH",
        "JNJ",
        "V",
        "XOM",
        "JPM",
        "PG",
        "MA",
        "HD",
        "CVX",
        "MRK",
        "ABBV",
        "LLY",
        "PEP",
        "KO",
        "COST",
        "TMO",
        "WMT",
        "AVGO",
        "MCD",
        "CSCO",
        "ACN",
        "ABT",
        "DHR",
        "BAC",
        "CRM",
        "WFC",
        "ADBE",
        "NKE",
        "TXN",
        "PM",
        "NEE",
        "UPS",
        "MS",
        "RTX",
        "ORCL",
        "HON",
        "INTC",
        "QCOM",
        "IBM",
        "BA",
        "AMD",
        "SBUX",
    ]


def main():
    """Main function to run hourly data ingestion"""
    ingestion = HourlyStockDataIngestion()

    symbols = get_sp500_symbols()

    logger.info(f"Starting hourly data ingestion for {len(symbols)} symbols")

    result = ingestion.update_all_symbols(symbols, period="1mo")

    logger.info(f"Results: {result['success_count']} succeeded, {result['error_count']} failed")

    return result


if __name__ == "__main__":
    main()
