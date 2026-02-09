"""Qdrant vector store helper for Qdrant service"""

import os
from typing import List

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

_qdrant_client = None


def get_qdrant_client():
    """Get or create Qdrant client"""
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient

        _qdrant_client = QdrantClient(
            host=QDRANT_HOST,
            port=QDRANT_PORT,
            check_compatibility=False,
        )
    return _qdrant_client


def get_qdrant_status() -> str:
    """Check Qdrant connection status"""
    try:
        client = get_qdrant_client()
        client.get_collections()
        return "connected"
    except Exception as e:
        return f"error: {str(e)}"


def list_collections() -> List[str]:
    """List all collections"""
    client = get_qdrant_client()
    collections = client.get_collections()
    return [c.name for c in collections.collections]


def create_collection(name: str, vector_size: int = 384, distance: str = "Cosine") -> bool:
    """Create a collection"""
    from qdrant_client.models import Distance, VectorParams

    client = get_qdrant_client()
    dist = Distance.COSINE if distance == "Cosine" else Distance.EUCLID

    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=vector_size, distance=dist),
    )
    return True
