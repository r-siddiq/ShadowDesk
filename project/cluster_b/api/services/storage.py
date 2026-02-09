"""Storage service for MinIO and Qdrant"""

import os
from typing import Dict, List, Optional

import numpy as np

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "stock_embeddings")

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


def add_embedding_to_qdrant(text: str, stock: Optional[str] = None) -> Dict:
    """Add embedding to Qdrant"""
    client = get_qdrant_client()

    vector = np.random.rand(384).astype(float).tolist()
    point_id = hash(text) % 1000000

    client.upsert(
        collection_name=QDRANT_COLLECTION,
        points=[
            {
                "id": point_id,
                "vector": vector,
                "payload": {"text": text, "stock": stock},
            }
        ],
    )

    return {"status": "added", "id": point_id, "text": text[:50]}


def search_embeddings_in_qdrant(query: str, limit: int = 5) -> List[Dict]:
    """Search embeddings in Qdrant"""
    client = get_qdrant_client()

    query_vector = np.random.rand(384).astype(float).tolist()

    results = client.query_points(collection_name=QDRANT_COLLECTION, query=query_vector, limit=limit)

    return [{"id": r.id, "score": r.score, "text": r.payload.get("text", "")} for r in results.points]


def get_qdrant_collections() -> Dict:
    """Get Qdrant collections"""
    client = get_qdrant_client()
    collections = client.get_collections()
    return {"collections": [c.name for c in collections.collections]}
