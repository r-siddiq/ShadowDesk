"""Configuration for CLUSTER_B API"""

import os


class Config:
    """Application configuration"""

    # API Settings
    APP_NAME: str = "ShadowDesk Trading API"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Server Settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # CLUSTER_A Services (MinIO)
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "stock-data")

    # CLUSTER_A Services (Qdrant)
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "stock_embeddings")

    # MLflow (CLUSTER_A)
    MLFLOW_TRACKING_URI: str = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:30368")

    # Model Settings
    MODEL_VERSION: str = os.getenv("MODEL_VERSION", "1.0.0")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "384"))


config = Config()
