from pathlib import Path
from uuid import uuid4
import json

from PIL import Image
import pytesseract

from app.knowledge.extractor import extract_text


BASE_DIR = Path(__file__).resolve().parent.parent

CHAT_UPLOADS_DIR = (
    BASE_DIR
    / "knowledge"
    / "chat_uploads"
)


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


def _extract_image_text(
    file_path: Path,
) -> str:
    """
    Extract visible text from an uploaded image
    using local Tesseract OCR.

    No external service is used.
    """

    try:
        with Image.open(file_path) as image:
            image = image.convert("RGB")

            extracted_text = pytesseract.image_to_string(
                image,
                config="--psm 6",
            )

    except Exception as exc:
        raise RuntimeError(
            f"Failed to process image with local OCR: {exc}"
        ) from exc

    return extracted_text


def _extract_chat_text(
    file_path: Path,
    extension: str,
) -> str:
    """
    Extract text from supported chat attachments.

    PDF/DOCX/TXT:
        Use NOVA's existing extractor.

    Images:
        Use local Tesseract OCR.
    """

    if extension in IMAGE_EXTENSIONS:
        return _extract_image_text(
            file_path
        )

    return extract_text(
        str(file_path)
    )


def save_chat_file(
    filename: str,
    file_bytes: bytes,
    content_type: str = "",
) -> dict:
    if not filename:
        raise ValueError(
            "No filename provided."
        )

    extension = (
        Path(filename)
        .suffix
        .lower()
    )

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. "
            "Use PDF, TXT, DOCX, PNG, JPG, JPEG, or WEBP."
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

    original_name = (
        Path(filename).name
    )

    stored_name = (
        f"{file_id}_{original_name}"
    )

    file_path = (
        CHAT_UPLOADS_DIR
        / stored_name
    )

    file_path.write_bytes(
        file_bytes
    )

    try:
        extracted_text = _extract_chat_text(
            file_path=file_path,
            extension=extension,
        )

    except Exception:
        if file_path.exists():
            file_path.unlink()

        raise

    extracted_text = (
        extracted_text
        .strip()
    )

    if not extracted_text:
        if file_path.exists():
            file_path.unlink()

        if extension in IMAGE_EXTENSIONS:
            raise ValueError(
                "No readable text was found in the image."
            )

        raise ValueError(
            "No readable text was found in the file."
        )

    metadata = {
        "file_id": file_id,
        "filename": original_name,
        "stored_name": stored_name,
        "content_type": content_type,
        "extension": extension,
        "file_type": (
            "image"
            if extension in IMAGE_EXTENSIONS
            else "document"
        ),
        "characters": len(
            extracted_text
        ),
        "text": extracted_text,
    }

    metadata_path = (
        CHAT_UPLOADS_DIR
        / f"{file_id}.json"
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
        "extension": extension,
        "file_type": (
            "image"
            if extension in IMAGE_EXTENSIONS
            else "document"
        ),
        "characters": len(
            extracted_text
        ),
    }


def load_chat_file(
    file_id: str,
) -> dict:
    metadata_path = (
        CHAT_UPLOADS_DIR
        / f"{file_id}.json"
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