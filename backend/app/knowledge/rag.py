from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from app.services.knowledge.extractor import extract_document

from .vector_store import (
    add_document,
    search_documents,
)


# ---------------------------------------------------------------------------
# DOCUMENT INDEXING
# ---------------------------------------------------------------------------

def index_document(
    file_path: str,
    file_id: Optional[str] = None,
    vault_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract a real local document and index its readable content.

    Physical file ownership remains with the NOVA file registry.
    ChromaDB stores searchable chunks and indexing metadata only.
    """

    path = Path(
        file_path
    ).resolve()

    if not path.exists():
        raise FileNotFoundError(
            f"Document does not exist: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Document path is not a file: {path}"
        )

    extraction = extract_document(
        str(path)
    )

    text = str(
        extraction.text or ""
    ).strip()

    if not text:
        raise ValueError(
            "No readable text was found in the document."
        )

    filename = path.name

    result = add_document(
        text=text,
        filename=filename,
        file_id=file_id,
        vault_id=vault_id,
        file_path=str(path),
        source=filename,
    )

    return {
        "filename": filename,
        "file_path": str(path),
        "file_type": extraction.file_type,
        "characters": len(text),
        "chunks": int(
            result.get(
                "chunks",
                0,
            )
            or 0
        ),
        "replaced": bool(
            result.get(
                "replaced",
                False,
            )
        ),
        "file_id": file_id,
        "vault_id": vault_id,
        "used_ocr": bool(
            extraction.used_ocr
        ),
        "pages": len(
            extraction.pages
        ),
        "metadata": extraction.metadata,
        "indexed": bool(
            result.get(
                "indexed",
                False,
            )
        ),
        "indexed_at": str(
            result.get(
                "indexed_at",
                "",
            )
            or ""
        ),
        "content_sha256": str(
            result.get(
                "content_sha256",
                extraction.metadata.get(
                    "sha256",
                    "",
                )
                if isinstance(
                    extraction.metadata,
                    dict,
                )
                else "",
            )
            or ""
        ),
    }


# ---------------------------------------------------------------------------
# KNOWLEDGE RETRIEVAL
# ---------------------------------------------------------------------------

def retrieve_context(
    query: str,
    top_k: int = 5,
    vault_id: Optional[str] = None,
) -> list[dict]:
    """
    Search indexed local knowledge.

    vault_id supplied:
        Search only that Knowledge Vault.

    vault_id omitted:
        Search all indexed local knowledge.
    """

    normalized_query = str(
        query or ""
    ).strip()

    if not normalized_query:
        return []

    return search_documents(
        query=normalized_query,
        top_k=top_k,
        vault_id=vault_id,
    )