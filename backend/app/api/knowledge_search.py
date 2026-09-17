from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.knowledge.rag import retrieve_context
from app.services.vault_manager import list_vaults


router = APIRouter(
    prefix="/api/knowledge",
    tags=["Knowledge Vault"],
)


# ---------------------------------------------------------------------------
# REQUEST MODEL
# ---------------------------------------------------------------------------

class KnowledgeSearchRequest(BaseModel):
    query: str

    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
    )

    vault_id: Optional[str] = None


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _normalize_vault_id(
    vault_id: Optional[str],
) -> Optional[str]:
    if vault_id is None:
        return None

    normalized = str(
        vault_id
    ).strip()

    if not normalized:
        return None

    if (
        "/" in normalized
        or "\\" in normalized
        or normalized in {
            ".",
            "..",
        }
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid vault_id.",
        )

    return normalized


def _validate_vault_exists(
    vault_id: Optional[str],
) -> None:
    if not vault_id:
        return

    try:
        vaults = list_vaults()

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to validate vault: {exc}"
            ),
        ) from exc

    exists = any(
        str(
            vault.get(
                "vault_id",
                "",
            )
        ).strip()
        == vault_id
        for vault in vaults
    )

    if not exists:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Vault not found: {vault_id}"
            ),
        )


def _normalize_result(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    file_id = result.get(
        "file_id"
    )

    vault_id = result.get(
        "vault_id"
    )

    filename = result.get(
        "filename"
    )

    source = result.get(
        "source"
    )

    chunk = result.get(
        "chunk",
        result.get(
            "chunk_index",
            0,
        ),
    )

    try:
        normalized_chunk = int(
            chunk
        )
    except (
        TypeError,
        ValueError,
    ):
        normalized_chunk = 0

    # The vector layer currently exposes the chunk number rather
    # than a separate chunk_id. Keep both forms available to the UI.
    chunk_id = result.get(
        "chunk_id"
    )

    if chunk_id is None:
        if file_id:
            chunk_id = (
                f"{file_id}-chunk-{normalized_chunk}"
            )
        else:
            chunk_id = str(
                normalized_chunk
            )

    text = str(
        result.get(
            "text",
            "",
        )
        or ""
    )

    source_value = str(
        source or filename or "unknown"
    ).strip()

    filename_value = str(
        filename or source_value
    ).strip()

    return {
        "text": text,
        "source": source_value,
        "filename": filename_value,
        "vault_id": vault_id,
        "file_id": file_id,
        "chunk": normalized_chunk,
        "chunk_id": str(
            chunk_id
        ),
        "path": result.get(
            "path",
            "",
        ),
        "score": result.get(
            "score"
        ),
    }


# ---------------------------------------------------------------------------
# SEARCH
# ---------------------------------------------------------------------------

@router.post("/search")
def search_knowledge(
    request: KnowledgeSearchRequest,
) -> Dict[str, Any]:
    query = str(
        request.query or ""
    ).strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty.",
        )

    vault_id = _normalize_vault_id(
        request.vault_id
    )

    _validate_vault_exists(
        vault_id
    )

    try:
        results = retrieve_context(
            query=query,
            top_k=request.top_k,
            vault_id=vault_id,
        )

        normalized_results: List[
            Dict[str, Any]
        ] = []

        for result in results:
            if not isinstance(
                result,
                dict,
            ):
                continue

            normalized_results.append(
                _normalize_result(
                    result
                )
            )

        return {
            "query": query,
            "vault_id": vault_id,
            "results": normalized_results,
            "count": len(
                normalized_results
            ),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Knowledge search failed: {exc}"
            ),
        ) from exc