from pathlib import Path
from uuid import uuid4
import json

from app.knowledge.extractor import extract_text


BASE_DIR = Path(__file__).resolve().parent.parent
CHAT_UPLOADS_DIR = BASE_DIR / "knowledge" / "chat_uploads"


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".docx",
}


def save_chat_file(
    filename: str,
    file_bytes: bytes,
    content_type: str = "",
) -> dict:
    if not filename:
        raise ValueError("No filename provided.")

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. "
            "Use PDF, TXT, or DOCX."
        )

    if not file_bytes:
        raise ValueError(
            "The uploaded file is empty."
        )

    max_size = 20 * 1024 * 1024

    if len(file_bytes) > max_size:
        raise ValueError(
            "File is too large. Maximum size is 20 MB."
        )

    CHAT_UPLOADS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_id = uuid4().hex

    original_name = Path(filename).name

    stored_name = (
        f"{file_id}_{original_name}"
    )

    file_path = CHAT_UPLOADS_DIR / stored_name

    file_path.write_bytes(file_bytes)

    try:
        extracted_text = extract_text(
            str(file_path)
        )
    except Exception:
        if file_path.exists():
            file_path.unlink()

        raise

    extracted_text = extracted_text.strip()

    if not extracted_text:
        if file_path.exists():
            file_path.unlink()

        raise ValueError(
            "No readable text was found in the file."
        )

    metadata = {
        "file_id": file_id,
        "filename": original_name,
        "stored_name": stored_name,
        "content_type": content_type,
        "characters": len(extracted_text),
        "text": extracted_text,
    }

    metadata_path = (
        CHAT_UPLOADS_DIR /
        f"{file_id}.json"
    )

    metadata_path.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return {
        "file_id": file_id,
        "filename": original_name,
        "stored_name": stored_name,
        "content_type": content_type,
        "characters": len(extracted_text),
    }


def load_chat_file(
    file_id: str,
) -> dict:
    metadata_path = (
        CHAT_UPLOADS_DIR /
        f"{file_id}.json"
    )

    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Attachment not found: {file_id}"
        )

    return json.loads(
        metadata_path.read_text(
            encoding="utf-8"
        )
    )