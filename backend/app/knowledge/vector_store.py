from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parent
VECTORSTORE_DIR = BASE_DIR / "vectorstore"

COLLECTION_NAME = "nova_knowledge"

_embedding_model = None
_chroma_client = None
_collection = None


def get_embedding_model():
    global _embedding_model

    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            "all-MiniLM-L6-v2"
        )

    return _embedding_model


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


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[str]:
    text = text.strip()

    if not text:
        return []

    chunks = []
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


def add_document(
    text: str,
    filename: str,
) -> dict:
    """
    Add a document to the local vector store.

    Existing chunks belonging to the same source
    are removed before the document is re-indexed.
    """

    chunks = chunk_text(text)

    if not chunks:
        return {
            "indexed": False,
            "chunks": 0,
            "replaced": False,
        }

    collection = get_collection()
    model = get_embedding_model()

    replaced = document_exists(filename)

    if replaced:
        delete_document(filename)

    embeddings = model.encode(
        chunks
    ).tolist()

    document_ids = [
        f"{filename}-{index}"
        for index in range(len(chunks))
    ]

    metadatas = [
        {
            "source": filename,
            "chunk": index,
        }
        for index in range(len(chunks))
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


def search_documents(
    query: str,
    top_k: int = 5,
) -> list[dict]:
    collection = get_collection()
    model = get_embedding_model()

    if collection.count() == 0:
        return []

    query_embedding = model.encode(
        [query]
    )[0].tolist()

    # Never ask Chroma for more results than
    # documents actually stored.
    n_results = min(
        top_k,
        collection.count(),
    )

    results = collection.query(
        query_embeddings=[
            query_embedding
        ],
        n_results=n_results,
    )

    documents = results.get(
        "documents",
        [[]],
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]],
    )[0]

    matches = []

    for document, metadata in zip(
        documents,
        metadatas,
    ):
        matches.append(
            {
                "text": document,
                "source": metadata.get(
                    "source",
                    "unknown",
                ),
                "chunk": metadata.get(
                    "chunk",
                    0,
                ),
            }
        )

    return matches