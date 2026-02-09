"""Embedding routes for vector storage"""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class EmbeddingRequest(BaseModel):
    text: str
    stock: Optional[str] = None


class EmbeddingResponse(BaseModel):
    status: str
    id: int
    text: str


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


class SearchResult(BaseModel):
    id: int
    score: float
    text: str


@router.post("/add", response_model=EmbeddingResponse)
async def add_embedding(request: EmbeddingRequest):
    """Add embedding to vector store"""
    from ..services.storage import add_embedding_to_qdrant

    result = add_embedding_to_qdrant(request.text, request.stock)
    return result


@router.get("/search")
async def search_embeddings(query: str, limit: int = 5):
    """Search embeddings"""
    from ..services.storage import search_embeddings_in_qdrant

    results = search_embeddings_in_qdrant(query, limit)
    return {"query": query, "results": results}


@router.get("/collections")
async def list_collections():
    """List Qdrant collections"""
    from ..services.storage import get_qdrant_collections

    return get_qdrant_collections()
