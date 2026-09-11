from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.knowledge.rag import retrieve_context


router = APIRouter(
    prefix="/api/knowledge",
    tags=["Knowledge Vault"],
)


class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/search")
def search_knowledge(request: KnowledgeSearchRequest):
    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty.",
        )

    if request.top_k < 1 or request.top_k > 10:
        raise HTTPException(
            status_code=400,
            detail="top_k must be between 1 and 10.",
        )

    try:
        results = retrieve_context(
            query=query,
            top_k=request.top_k,
        )

        return {
            "query": query,
            "results": results,
            "count": len(results),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Knowledge search failed: {exc}",
        ) from exc