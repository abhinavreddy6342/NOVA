from pathlib import Path

from .extractor import extract_text
from .vector_store import (
    add_document,
    search_documents,
)


def index_document(
    file_path: str,
) -> dict:
    text = extract_text(file_path)

    if not text.strip():
        raise ValueError(
            "No readable text was found in the document."
        )

    filename = Path(
        file_path
    ).name

    result = add_document(
        text=text,
        filename=filename,
    )

    return {
        "filename": filename,
        "characters": len(text),
        "chunks": result["chunks"],
        "replaced": result["replaced"],
    }


def retrieve_context(
    query: str,
    top_k: int = 5,
) -> list[dict]:
    return search_documents(
        query=query,
        top_k=top_k,
    )