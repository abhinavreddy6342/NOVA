from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from sentence_transformers import SentenceTransformer


# ---------------------------------------------------------------------------
# STORAGE
# ---------------------------------------------------------------------------

BASE_DIR = Path(
    __file__
).resolve().parent

VECTORSTORE_DIR = (
    BASE_DIR / "vectorstore"
).resolve()

COLLECTION_NAME = "nova_knowledge"

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

_embedding_model: Optional[
    SentenceTransformer
] = None

_chroma_client = None
_collection = None


# ---------------------------------------------------------------------------
# EMBEDDINGS
# ---------------------------------------------------------------------------

def get_embedding_model() -> SentenceTransformer:
    """
    Lazily load the local embedding model.

    The model is kept in memory after the first load so repeated
    Knowledge Vault searches do not reload it.
    """

    global _embedding_model

    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            EMBEDDING_MODEL_NAME
        )

    return _embedding_model


# ---------------------------------------------------------------------------
# COLLECTION
# ---------------------------------------------------------------------------

def get_collection():
    """
    Return the persistent NOVA Chroma collection.

    Chroma stores searchable vectors and metadata only.
    The Knowledge Vault registry remains the file-management
    source of truth.
    """

    global _chroma_client
    global _collection

    if _collection is None:
        VECTORSTORE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        _chroma_client = chromadb.PersistentClient(
            path=str(
                VECTORSTORE_DIR
            )
        )

        _collection = (
            _chroma_client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={
                    "description": (
                        "NOVA local knowledge index. "
                        "The local file registry remains the source of truth."
                    ),
                    "version": "2",
                },
            )
        )

    return _collection


# ---------------------------------------------------------------------------
# CHUNKING
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 120,
) -> List[str]:
    """
    Split text into deterministic overlapping character chunks.

    Character-based chunking is intentionally preserved because
    existing NOVA indexing and retrieval were built around it.
    """

    value = str(
        text or ""
    ).strip()

    if not value:
        return []

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than zero."
        )

    if overlap < 0:
        raise ValueError(
            "overlap cannot be negative."
        )

    if overlap >= chunk_size:
        raise ValueError(
            "overlap must be smaller than chunk_size."
        )

    chunks: List[str] = []

    start = 0
    text_length = len(value)

    while start < text_length:
        end = min(
            start + chunk_size,
            text_length,
        )

        chunk = value[
            start:end
        ].strip()

        if chunk:
            chunks.append(
                chunk
            )

        if end >= text_length:
            break

        start = end - overlap

    return chunks


# ---------------------------------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------------------------------

def _normalize_file_id(
    file_id: Optional[str],
) -> str:
    return str(
        file_id or ""
    ).strip()


def _normalize_vault_id(
    vault_id: Optional[str],
) -> str:
    return str(
        vault_id or ""
    ).strip()


def _normalize_filename(
    filename: str,
) -> str:
    return Path(
        str(
            filename or ""
        )
    ).name.strip()


def _normalize_path(
    file_path: Optional[str],
) -> str:
    value = str(
        file_path or ""
    ).strip()

    if not value:
        return ""

    try:
        return str(
            Path(value).resolve()
        )
    except Exception:
        return value


def _normalize_source(
    source: Optional[str],
) -> str:
    return str(
        source or ""
    ).strip()


# ---------------------------------------------------------------------------
# METADATA
# ---------------------------------------------------------------------------

def _utc_timestamp() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _content_sha256(
    text: str,
) -> str:
    return hashlib.sha256(
        str(
            text or ""
        ).encode(
            "utf-8"
        )
    ).hexdigest()


# ---------------------------------------------------------------------------
# DOCUMENT IDENTITY
# ---------------------------------------------------------------------------

def _stable_identity(
    file_id: str,
    filename: str,
) -> str:
    normalized_file_id = _normalize_file_id(
        file_id
    )

    if normalized_file_id:
        return normalized_file_id

    normalized_filename = _normalize_filename(
        filename
    )

    if normalized_filename:
        return normalized_filename

    return "legacy-empty-document"


def _stable_chunk_id(
    file_id: str,
    filename: str,
    chunk_index: int,
) -> str:
    identity = _stable_identity(
        file_id=file_id,
        filename=filename,
    )

    digest = hashlib.sha1(
        identity.encode(
            "utf-8"
        )
    ).hexdigest()[:20]

    return (
        f"nova-{digest}-chunk-{chunk_index}"
    )


# ---------------------------------------------------------------------------
# DOCUMENT LOOKUPS
# ---------------------------------------------------------------------------

def document_exists(
    filename: str = "",
    file_id: Optional[str] = None,
) -> bool:
    """
    Determine whether at least one Chroma chunk exists for a logical file.

    file_id is the canonical identity.
    Filename is retained as a legacy fallback.
    """

    collection = get_collection()

    normalized_file_id = _normalize_file_id(
        file_id
    )

    normalized_filename = _normalize_filename(
        filename
    )

    if not normalized_file_id and not normalized_filename:
        return False

    try:
        if normalized_file_id:
            results = collection.get(
                where={
                    "file_id": normalized_file_id,
                },
                limit=1,
            )

        else:
            results = collection.get(
                where={
                    "filename": normalized_filename,
                },
                limit=1,
            )

        return bool(
            results.get(
                "ids"
            )
        )

    except Exception as exc:
        print(
            "[NOVA VECTOR LOOKUP] "
            f"{type(exc).__name__}: {exc}"
        )
        return False


def delete_document(
    filename: str = "",
    file_id: Optional[str] = None,
) -> None:
    """
    Delete all indexed chunks for one logical file.

    file_id is the canonical identity.
    Filename is a legacy fallback.
    """

    collection = get_collection()

    normalized_file_id = _normalize_file_id(
        file_id
    )

    normalized_filename = _normalize_filename(
        filename
    )

    if normalized_file_id:
        try:
            collection.delete(
                where={
                    "file_id": normalized_file_id,
                }
            )
        except Exception as exc:
            print(
                "[NOVA VECTOR DELETE BY FILE ID] "
                f"{type(exc).__name__}: {exc}"
            )

        return

    if normalized_filename:
        try:
            collection.delete(
                where={
                    "filename": normalized_filename,
                }
            )
        except Exception as exc:
            print(
                "[NOVA VECTOR DELETE BY FILENAME] "
                f"{type(exc).__name__}: {exc}"
            )


def get_document_chunks(
    file_id: str,
) -> List[Dict[str, Any]]:
    """
    Return every indexed chunk belonging to one file.

    This is useful for diagnostics, preview tooling, and future
    audit/version functionality.
    """

    normalized_file_id = _normalize_file_id(
        file_id
    )

    if not normalized_file_id:
        return []

    collection = get_collection()

    try:
        result = collection.get(
            where={
                "file_id": normalized_file_id,
            },
            include=[
                "documents",
                "metadatas",
            ],
        )

    except Exception as exc:
        print(
            "[NOVA VECTOR GET CHUNKS] "
            f"{type(exc).__name__}: {exc}"
        )
        return []

    ids = result.get(
        "ids",
        [],
    ) or []

    documents = result.get(
        "documents",
        [],
    ) or []

    metadatas = result.get(
        "metadatas",
        [],
    ) or []

    output: List[
        Dict[str, Any]
    ] = []

    for index, chunk_id in enumerate(
        ids
    ):
        metadata = (
            metadatas[index]
            if index < len(metadatas)
            and isinstance(
                metadatas[index],
                dict,
            )
            else {}
        )

        document = (
            documents[index]
            if index < len(documents)
            else ""
        )

        output.append(
            {
                "id": str(
                    chunk_id
                ),
                "text": str(
                    document or ""
                ),
                "metadata": dict(
                    metadata
                ),
            }
        )

    return output


# ---------------------------------------------------------------------------
# ADD / INDEX
# ---------------------------------------------------------------------------

def add_document(
    text: str,
    filename: str,
    file_id: Optional[str] = None,
    vault_id: Optional[str] = None,
    file_path: Optional[str] = None,
    source: Optional[str] = None,
) -> dict:
    """
    Replace the complete Chroma representation of one logical file.

    Chroma stores:
        - chunk text
        - embeddings
        - searchable metadata
        - indexing timestamps
        - content checksum

    The physical file and its lifecycle are managed by
    vault_manager.py.
    """

    normalized_filename = _normalize_filename(
        filename
    )

    normalized_file_id = _normalize_file_id(
        file_id
    )

    normalized_vault_id = _normalize_vault_id(
        vault_id
    )

    normalized_path = _normalize_path(
        file_path
    )

    normalized_source = _normalize_source(
        source
    )

    if not normalized_filename:
        raise ValueError(
            "A valid filename is required for indexing."
        )

    value = str(
        text or ""
    ).strip()

    chunks = chunk_text(
        value
    )

    # Empty extraction means there should not be stale vectors
    # remaining for this file.
    if not chunks:
        if normalized_file_id:
            delete_document(
                file_id=normalized_file_id
            )
        else:
            delete_document(
                filename=normalized_filename
            )

        return {
            "indexed": False,
            "chunks": 0,
            "replaced": False,
        }

    collection = get_collection()
    model = get_embedding_model()

    replaced = document_exists(
        filename=normalized_filename,
        file_id=(
            normalized_file_id
            or None
        ),
    )

    # Remove the complete old logical representation before
    # inserting the fresh representation.
    if normalized_file_id:
        delete_document(
            file_id=normalized_file_id
        )

    elif replaced:
        delete_document(
            filename=normalized_filename
        )

    embeddings = model.encode(
        chunks,
        show_progress_bar=False,
    ).tolist()

    document_ids = [
        _stable_chunk_id(
            file_id=normalized_file_id,
            filename=normalized_filename,
            chunk_index=index,
        )
        for index in range(
            len(chunks)
        )
    ]

    resolved_source = (
        normalized_source
        or normalized_filename
    )

    indexed_at = _utc_timestamp()
    content_sha256 = _content_sha256(
        value
    )

    metadatas = [
        {
            "source": resolved_source,
            "filename": normalized_filename,
            "file_id": normalized_file_id,
            "vault_id": normalized_vault_id,
            "path": normalized_path,
            "chunk": index,
            "chunk_index": index,
            "indexed_at": indexed_at,
            "content_sha256": content_sha256,
            "index_version": "2",
        }
        for index in range(
            len(chunks)
        )
    ]

    collection.add(
        ids=document_ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return {
        "indexed": True,
        "chunks": len(chunks),
        "replaced": replaced,
        "content_sha256": content_sha256,
        "indexed_at": indexed_at,
    }


# ---------------------------------------------------------------------------
# SEARCH HELPERS
# ---------------------------------------------------------------------------

_STOP_WORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "for",
    "to",
    "of",
    "in",
    "on",
    "at",
    "and",
    "or",
    "with",
    "from",
    "by",
    "about",
    "what",
    "which",
    "where",
    "when",
    "how",
    "can",
    "could",
    "would",
    "should",
    "please",
    "me",
    "my",
    "show",
    "tell",
    "give",
    "find",
    "search",
    "look",
    "local",
    "knowledge",
    "base",
    "document",
    "documents",
    "file",
    "files",
}


def _tokenize(
    text: str,
) -> List[str]:
    tokens = re.findall(
        r"[a-z0-9]+",
        str(
            text or ""
        ).lower(),
    )

    return [
        token
        for token in tokens
        if (
            token not in _STOP_WORDS
            and len(token) > 1
        )
    ]


def _lexical_score(
    query: str,
    document: str,
    source: str,
) -> float:
    query_tokens = set(
        _tokenize(query)
    )

    if not query_tokens:
        return 0.0

    document_tokens = set(
        _tokenize(document)
    )

    source_tokens = set(
        _tokenize(source)
    )

    document_matches = (
        query_tokens
        & document_tokens
    )

    source_matches = (
        query_tokens
        & source_tokens
    )

    document_score = (
        len(document_matches)
        / len(query_tokens)
    )

    source_score = (
        len(source_matches)
        / len(query_tokens)
    )

    return (
        document_score * 0.85
        + source_score * 0.15
    )


def _is_low_information(
    text: str,
) -> bool:
    normalized = re.sub(
        r"\s+",
        " ",
        str(
            text or ""
        ),
    ).strip()

    if len(normalized) < 40:
        return True

    tokens = _tokenize(
        normalized
    )

    return len(tokens) < 8


def _similarity_from_distance(
    distance: Any,
) -> float:
    try:
        value = float(
            distance
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0.0

    if value < 0:
        value = 0.0

    return 1.0 / (
        1.0 + value
    )


def _safe_metadata(
    metadata: Any,
) -> Dict[str, Any]:
    if isinstance(
        metadata,
        dict,
    ):
        return dict(
            metadata
        )

    return {}


def _safe_chunk_value(
    value: Any,
) -> int:
    try:
        return int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0


# ---------------------------------------------------------------------------
# SEARCH
# ---------------------------------------------------------------------------

def search_documents(
    query: str,
    top_k: int = 5,
    vault_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Hybrid local search.

    Ranking combines:
        - semantic similarity from the embedding model
        - lexical token overlap
        - source/filename relevance

    When vault_id is supplied, Chroma performs a metadata-level
    vault filter before NOVA applies final ranking and deduplication.
    """

    normalized_query = str(
        query or ""
    ).strip()

    if not normalized_query:
        return []

    try:
        normalized_top_k = int(
            top_k
        )
    except (
        TypeError,
        ValueError,
    ):
        normalized_top_k = 5

    normalized_top_k = max(
        1,
        min(
            normalized_top_k,
            20,
        ),
    )

    normalized_vault_id = _normalize_vault_id(
        vault_id
    )

    collection = get_collection()
    model = get_embedding_model()

    try:
        total_documents = int(
            collection.count()
        )
    except Exception as exc:
        print(
            "[NOVA VECTOR COUNT] "
            f"{type(exc).__name__}: {exc}"
        )
        return []

    if total_documents <= 0:
        return []

    try:
        query_embedding = model.encode(
            [normalized_query],
            show_progress_bar=False,
        )[0].tolist()
    except Exception as exc:
        print(
            "[NOVA VECTOR EMBEDDING] "
            f"{type(exc).__name__}: {exc}"
        )
        return []

    # Retrieve enough candidates to allow lexical reranking and
    # duplicate suppression before returning the requested top_k.
    candidate_count = min(
        max(
            normalized_top_k * 8,
            20,
        ),
        total_documents,
    )

    query_kwargs: Dict[
        str,
        Any,
    ] = {
        "query_embeddings": [
            query_embedding
        ],
        "n_results": candidate_count,
        "include": [
            "documents",
            "metadatas",
            "distances",
        ],
    }

    if normalized_vault_id:
        query_kwargs["where"] = {
            "vault_id": normalized_vault_id,
        }

    try:
        results = collection.query(
            **query_kwargs
        )

    except Exception as exc:
        print(
            "[NOVA VECTOR SEARCH] "
            f"{type(exc).__name__}: {exc}"
        )
        return []

    raw_documents = results.get(
        "documents"
    )

    raw_metadatas = results.get(
        "metadatas"
    )

    raw_distances = results.get(
        "distances"
    )

    documents = (
        raw_documents[0]
        if raw_documents
        and len(raw_documents) > 0
        else []
    )

    metadatas = (
        raw_metadatas[0]
        if raw_metadatas
        and len(raw_metadatas) > 0
        else []
    )

    distances = (
        raw_distances[0]
        if raw_distances
        and len(raw_distances) > 0
        else []
    )

    candidates: List[
        Dict[str, Any]
    ] = []

    for (
        document,
        metadata,
        distance,
    ) in zip(
        documents,
        metadatas,
        distances,
    ):
        if not document:
            continue

        metadata = _safe_metadata(
            metadata
        )

        source = str(
            metadata.get(
                "source",
                "",
            )
            or ""
        ).strip()

        filename = str(
            metadata.get(
                "filename",
                "",
            )
            or source
            or "unknown"
        ).strip()

        file_id = str(
            metadata.get(
                "file_id",
                "",
            )
            or ""
        ).strip()

        indexed_vault_id = str(
            metadata.get(
                "vault_id",
                "",
            )
            or ""
        ).strip()

        indexed_path = str(
            metadata.get(
                "path",
                "",
            )
            or ""
        ).strip()

        if (
            normalized_vault_id
            and indexed_vault_id
            != normalized_vault_id
        ):
            continue

        document_text = str(
            document
        )

        if _is_low_information(
            document_text
        ):
            continue

        semantic_score = (
            _similarity_from_distance(
                distance
            )
        )

        lexical_score = (
            _lexical_score(
                normalized_query,
                document_text,
                f"{filename} {source}",
            )
        )

        combined_score = (
            semantic_score * 0.70
            + lexical_score * 0.30
        )

        chunk_value = metadata.get(
            "chunk",
            metadata.get(
                "chunk_index",
                0,
            ),
        )

        normalized_chunk = _safe_chunk_value(
            chunk_value
        )

        candidates.append(
            {
                "text": document_text,
                "source": (
                    source
                    or filename
                    or "unknown"
                ),
                "filename": (
                    filename
                    or source
                    or "unknown"
                ),
                "chunk": normalized_chunk,
                "file_id": file_id,
                "vault_id": indexed_vault_id,
                "path": indexed_path,
                "score": float(
                    combined_score
                ),
                "indexed_at": str(
                    metadata.get(
                        "indexed_at",
                        "",
                    )
                    or ""
                ),
                "content_sha256": str(
                    metadata.get(
                        "content_sha256",
                        "",
                    )
                    or ""
                ),
            }
        )

    candidates.sort(
        key=lambda item: float(
            item.get(
                "score",
                0.0,
            )
        ),
        reverse=True,
    )

    selected: List[
        Dict[str, Any]
    ] = []

    seen_chunks = set()
    seen_texts = set()

    for candidate in candidates:
        candidate_file_id = str(
            candidate.get(
                "file_id",
                "",
            )
            or ""
        )

        candidate_chunk = _safe_chunk_value(
            candidate.get(
                "chunk",
                0,
            )
        )

        # For normal NOVA files, file_id is always available.
        # The filename fallback keeps legacy indexed documents
        # deduplicated as well.
        identity = (
            candidate_file_id
            or str(
                candidate.get(
                    "filename",
                    "",
                )
                or ""
            )
        )

        chunk_id = (
            identity,
            candidate_chunk,
        )

        normalized_text = re.sub(
            r"\s+",
            " ",
            str(
                candidate.get(
                    "text",
                    "",
                )
            ).lower(),
        ).strip()

        if (
            chunk_id in seen_chunks
            or (
                normalized_text
                and normalized_text
                in seen_texts
            )
        ):
            continue

        seen_chunks.add(
            chunk_id
        )

        if normalized_text:
            seen_texts.add(
                normalized_text
            )

        selected.append(
            candidate
        )

        if len(selected) >= normalized_top_k:
            break

    return [
        {
            "text": item["text"],
            "source": item["source"],
            "filename": item["filename"],
            "chunk": item["chunk"],
            "file_id": item["file_id"],
            "vault_id": item["vault_id"],
            "path": item["path"],
            "score": item["score"],
            "indexed_at": item.get(
                "indexed_at",
                "",
            ),
            "content_sha256": item.get(
                "content_sha256",
                "",
            ),
        }
        for item in selected
    ]


# ---------------------------------------------------------------------------
# INDEX HEALTH / COUNTS
# ---------------------------------------------------------------------------

def get_index_stats() -> Dict[str, Any]:
    """
    Return real Chroma statistics for Knowledge Vault health views.
    """

    collection = get_collection()

    try:
        total_chunks = int(
            collection.count()
        )
    except Exception as exc:
        print(
            "[NOVA VECTOR STATS] "
            f"{type(exc).__name__}: {exc}"
        )
        total_chunks = 0

    return {
        "collection": COLLECTION_NAME,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "chunks": total_chunks,
        "storage_path": str(
            VECTORSTORE_DIR
        ),
    }