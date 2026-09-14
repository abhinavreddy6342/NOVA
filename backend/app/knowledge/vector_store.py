from pathlib import Path
import re
from typing import Any, Dict, List

import chromadb
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parent
VECTORSTORE_DIR = BASE_DIR / "vectorstore"

COLLECTION_NAME = "nova_knowledge"

_embedding_model = None
_chroma_client = None
_collection = None


# ---------------------------------------------------------------------------
# EMBEDDING MODEL
# ---------------------------------------------------------------------------

def get_embedding_model():
    global _embedding_model

    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            "all-MiniLM-L6-v2"
        )

    return _embedding_model


# ---------------------------------------------------------------------------
# CHROMA COLLECTION
# ---------------------------------------------------------------------------

def get_collection():
    global _chroma_client
    global _collection

    if _collection is None:
        VECTORSTORE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        _chroma_client = chromadb.PersistentClient(
            path=str(VECTORSTORE_DIR)
        )

        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME
        )

    return _collection


# ---------------------------------------------------------------------------
# TEXT CHUNKING
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 120,
) -> List[str]:
    """
    Split text into overlapping chunks.
    """

    text = text.strip()

    if not text:
        return []

    chunks: List[str] = []

    start = 0

    while start < len(text):
        end = start + chunk_size

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks


# ---------------------------------------------------------------------------
# DOCUMENT MANAGEMENT
# ---------------------------------------------------------------------------

def document_exists(
    filename: str,
) -> bool:
    collection = get_collection()

    results = collection.get(
        where={
            "source": filename,
        },
        limit=1,
    )

    return bool(
        results.get("ids")
    )


def delete_document(
    filename: str,
) -> None:
    collection = get_collection()

    collection.delete(
        where={
            "source": filename,
        }
    )


# ---------------------------------------------------------------------------
# INDEX DOCUMENT
# ---------------------------------------------------------------------------

def add_document(
    text: str,
    filename: str,
) -> dict:
    """
    Add a document to the local vector database.

    Existing chunks for the same source are removed
    before re-indexing.
    """

    chunks = chunk_text(
        text
    )

    if not chunks:
        return {
            "indexed": False,
            "chunks": 0,
            "replaced": False,
        }

    collection = get_collection()
    model = get_embedding_model()

    replaced = document_exists(
        filename
    )

    if replaced:
        delete_document(
            filename
        )

    embeddings = model.encode(
        chunks
    ).tolist()

    document_ids = [
        f"{filename}-{index}"
        for index in range(
            len(chunks)
        )
    ]

    metadatas = [
        {
            "source": filename,
            "chunk": index,
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
}


def _tokenize(
    text: str,
) -> List[str]:
    """
    Normalize text into searchable tokens.
    """

    tokens = re.findall(
        r"[a-z0-9]+",
        text.lower(),
    )

    return [
        token
        for token in tokens
        if token not in _STOP_WORDS
        and len(token) > 1
    ]


def _lexical_score(
    query: str,
    document: str,
    source: str,
) -> float:
    """
    Calculate lexical relevance from query terms.
    """

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
    """
    Filter chunks containing too little useful text.
    """

    normalized = re.sub(
        r"\s+",
        " ",
        text,
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
    """
    Convert Chroma distance into a similarity-like score.

    Lower distance produces a higher score.
    """

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


# ---------------------------------------------------------------------------
# SEARCH
# ---------------------------------------------------------------------------

def search_documents(
    query: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search the local NOVA knowledge base.

    Pipeline:

    semantic retrieval
        ↓
    larger candidate pool
        ↓
    lexical relevance
        ↓
    combined ranking
        ↓
    duplicate filtering
        ↓
    final top_k
    """

    query = query.strip()

    if not query:
        return []

    top_k = int(
        top_k
    )

    top_k = max(
        1,
        min(
            top_k,
            10,
        ),
    )

    collection = get_collection()
    model = get_embedding_model()

    total_documents = collection.count()

    if total_documents == 0:
        return []

    query_embedding = model.encode(
        [query]
    )[0].tolist()

    # ---------------------------------------------------------------
    # Retrieve more candidates than we finally return.
    # ---------------------------------------------------------------

    candidate_count = min(
        max(
            top_k * 5,
            15,
        ),
        total_documents,
    )

    results = collection.query(
        query_embeddings=[
            query_embedding
        ],
        n_results=candidate_count,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    documents = results.get(
        "documents",
        [[]],
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]],
    )[0]

    distances = results.get(
        "distances",
        [[]],
    )[0]

    candidates: List[Dict[str, Any]] = []

    # ---------------------------------------------------------------
    # Score candidates.
    # ---------------------------------------------------------------

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

        metadata = (
            metadata
            if isinstance(
                metadata,
                dict,
            )
            else {}
        )

        source = str(
            metadata.get(
                "source",
                "unknown",
            )
        )

        if _is_low_information(
            document
        ):
            continue

        semantic_score = (
            _similarity_from_distance(
                distance
            )
        )

        lexical_score = (
            _lexical_score(
                query=query,
                document=document,
                source=source,
            )
        )

        # Semantic relevance remains dominant.
        combined_score = (
            semantic_score * 0.70
            + lexical_score * 0.30
        )

        candidates.append(
            {
                "text": document,
                "source": source,
                "chunk": metadata.get(
                    "chunk",
                    0,
                ),
                "score": combined_score,
            }
        )

    # ---------------------------------------------------------------
    # Rank candidates.
    # ---------------------------------------------------------------

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    # ---------------------------------------------------------------
    # Remove duplicate text.
    # ---------------------------------------------------------------

    selected: List[
        Dict[str, Any]
    ] = []

    seen_texts = set()

    for candidate in candidates:
        normalized_text = re.sub(
            r"\s+",
            " ",
            candidate["text"].lower(),
        ).strip()

        if normalized_text in seen_texts:
            continue

        seen_texts.add(
            normalized_text
        )

        selected.append(
            candidate
        )

        if len(selected) >= top_k:
            break

    # ---------------------------------------------------------------
    # Public result format.
    # ---------------------------------------------------------------

    matches: List[
        Dict[str, Any]
    ] = []

    for candidate in selected:
        matches.append(
            {
                "text": candidate["text"],
                "source": candidate["source"],
                "chunk": candidate["chunk"],
            }
        )

    return matches