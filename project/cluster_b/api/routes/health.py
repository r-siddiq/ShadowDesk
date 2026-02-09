"""Health check routes"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str = "secondary-api"


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy")


@router.get("/health/services", response_model=dict)
async def services_health():
    from shared.storage.minio_helper import get_minio_status
    from shared.storage.qdrant_helper import get_qdrant_status

    return {
        "minio": get_minio_status(),
        "qdrant": get_qdrant_status(),
        "api": "running",
    }
