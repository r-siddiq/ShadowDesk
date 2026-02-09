"""
Dashboard Configuration
Manages settings, Vault integration, and API connections
"""

import logging
import os

logger = logging.getLogger(__name__)


class DashboardConfig:
    """Dashboard configuration manager"""

    # API Endpoints
    FASTAPI_BASE = os.getenv("FASTAPI_BASE", "http://localhost:8000")
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
    VAULT_URL = os.getenv("VAULT_URL", "http://localhost:8200")
    VAULT_TOKEN = os.getenv("VAULT_TOKEN", "")

    # Dashboard Settings
    REFRESH_INTERVAL = int(os.getenv("DASHBOARD_REFRESH", "2"))  # seconds
    LOG_LINES = int(os.getenv("LOG_LINES", "10"))

    # Risk Parameters (defaults)
    DEFAULT_MAX_POSITIONS = 10
    DEFAULT_POSITION_SIZE_PCT = 0.02  # 2%
    DEFAULT_STOP_LOSS_PCT = 0.15  # 15%
    DEFAULT_MAX_TOTAL_RISK = 0.25  # 25%
    DEFAULT_MIN_CONFIDENCE = 0.60  # 60%

    # Default Watchlist
    DEFAULT_WATCHLIST = [
        "AAPL",
        "GOOGL",
        "MSFT",
        "AMZN",
        "TSLA",
        "NVDA",
        "META",
        "NFLX",
        "AMD",
        "INTC",
        "BA",
        "JPM",
        "V",
        "MA",
        "PYPL",
        "DIS",
        "KO",
        "PEP",
        "WMT",
        "COST",
        "NKE",
        "SBUX",
        "CRM",
        "ADBE",
        "ORCL",
    ]

    # Vault paths
    VAULT_SECRET_PATH = "secret/data/trading"
    VAULT_API_KEY_PATH = "secret/data/alpaca"

    @classmethod
    def get_risk_params(cls) -> dict:
        """Get risk parameters from Vault or defaults"""
        try:
            import hvac

            client = hvac.Client(url=cls.VAULT_URL, token=cls.VAULT_TOKEN)
            if client.is_authenticated():
                secret = client.read(cls.VAULT_SECRET_PATH)
                if secret and "data" in secret:
                    return secret["data"]["data"]
        except Exception as e:
            logger.warning("Vault read failed for risk params, using defaults: %s", e)

        return {
            "max_positions": cls.DEFAULT_MAX_POSITIONS,
            "position_size_pct": cls.DEFAULT_POSITION_SIZE_PCT,
            "stop_loss_pct": cls.DEFAULT_STOP_LOSS_PCT,
            "max_total_risk": cls.DEFAULT_MAX_TOTAL_RISK,
            "min_confidence": cls.DEFAULT_MIN_CONFIDENCE,
            "watchlist": cls.DEFAULT_WATCHLIST,
        }

    @classmethod
    def save_risk_params(cls, params: dict) -> bool:
        """Save risk parameters to Vault"""
        try:
            import hvac

            client = hvac.Client(url=cls.VAULT_URL, token=cls.VAULT_TOKEN)
            if client.is_authenticated():
                client.write(cls.VAULT_SECRET_PATH, **params)
                return True
        except Exception as e:
            logger.warning("Vault write failed for risk params: %s", e)
        return False

    @classmethod
    def get_alpaca_keys(cls) -> dict:
        """Get Alpaca API keys from Vault"""
        try:
            import hvac

            client = hvac.Client(url=cls.VAULT_URL, token=cls.VAULT_TOKEN)
            if client.is_authenticated():
                secret = client.read(cls.VAULT_API_KEY_PATH)
                if secret and "data" in secret:
                    return secret["data"]["data"]
        except Exception as e:
            logger.warning("Vault read failed for Alpaca credentials: %s", e)
        return {"api_key": "", "secret_key": ""}

    @classmethod
    def save_alpaca_keys(cls, api_key: str, secret_key: str) -> bool:
        """Save Alpaca API keys to Vault"""
        try:
            import hvac

            client = hvac.Client(url=cls.VAULT_URL, token=cls.VAULT_TOKEN)
            if client.is_authenticated():
                client.write(cls.VAULT_API_KEY_PATH, api_key=api_key, secret_key=secret_key)
                return True
        except Exception as e:
            logger.warning("Vault write failed for Alpaca credentials: %s", e)
        return False
