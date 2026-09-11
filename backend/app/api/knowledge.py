from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.knowledge.rag import index_document


router = APIRouter(
    prefix="/api/knowledge",
    tags=["Knowledge Vault"],
)


BASE_DIR = Path(__file__).resolve().parent.parent
DOCUMENTS_DIR = BASE_DIR / "knowledge" / "documents"

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".docx",
}


@router.get("/health")
def knowledge_health():
    return {
        "status": "ready",
        "service": "nova-knowledge",
    }


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided.",
        )

    extension = Path(file.filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. "
                "Use PDF, TXT, or DOCX."
            ),
        )

    DOCUMENTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_name = (
        f"{uuid4().hex[:12]}_"
        f"{Path(file.filename).name}"
    )

    file_path = DOCUMENTS_DIR / safe_name

    try:
        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty.",
            )

        file_path.write_bytes(file_bytes)

        result = index_document(
            str(file_path)
        )

        return {
    "status": "indexed",
    "filename": file.filename,
    "stored_as": safe_name,
    "characters": result["characters"],
    "chunks": result["chunks"],
    "replaced_existing": result["replaced"],
}

    except HTTPException:
        if file_path.exists():
            file_path.unlink()

        raise

    except Exception as exc:
        if file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=500,
            detail=f"Document indexing failed: {exc}",
        ) from exc