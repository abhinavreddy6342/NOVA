from io import BytesIO
from pathlib import Path

import pymupdf
import pytesseract
from docx import Document
from PIL import Image


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".docx",
}

# Explicit Windows Tesseract installation path.
# This avoids relying on the system PATH used by Uvicorn.
TESSERACT_PATH = Path(
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

if TESSERACT_PATH.exists():
    pytesseract.pytesseract.tesseract_cmd = str(
        TESSERACT_PATH
    )


def extract_text(file_path: str) -> str:
    """
    Extract text from supported document formats.

    PDF:
    1. Try native PDF text extraction.
    2. If insufficient, render pages.
    3. Run Tesseract OCR locally.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {extension}. "
            f"Supported types: "
            f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if extension == ".txt":
        return path.read_text(
            encoding="utf-8",
            errors="ignore",
        ).strip()

    if extension == ".docx":
        return extract_docx(path)

    if extension == ".pdf":
        return extract_pdf(path)

    return ""


def extract_docx(path: Path) -> str:
    document = Document(path)

    parts = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()

        if text:
            parts.append(text)

    return "\n".join(parts).strip()


def extract_pdf(path: Path) -> str:
    document = pymupdf.open(str(path))

    try:
        native_parts = []

        for page in document:
            text = page.get_text("text").strip()

            if text:
                native_parts.append(text)

        native_text = "\n\n".join(
            native_parts
        ).strip()

        # Use native PDF text when available.
        if len(native_text) >= 50:
            return native_text

        print(
            "Native PDF text extraction returned "
            "little/no text."
        )
        print("Starting local OCR fallback...")

        if not TESSERACT_PATH.exists():
            raise RuntimeError(
                "Tesseract was not found at: "
                f"{TESSERACT_PATH}"
            )

        ocr_parts = []

        for page_number, page in enumerate(document):
            print(
                f"OCR processing page "
                f"{page_number + 1}/"
                f"{document.page_count}..."
            )

            # Render page at high resolution.
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(3, 3),
                colorspace=pymupdf.csRGB,
                alpha=False,
            )

            png_bytes = pixmap.tobytes("png")

            image = Image.open(
                BytesIO(png_bytes)
            ).convert("RGB")

            text = pytesseract.image_to_string(
                image,
                lang="eng",
                config="--psm 3",
            ).strip()

            if text:
                ocr_parts.append(
                    f"[Page {page_number + 1}]\n{text}"
                )

        return "\n\n".join(
            ocr_parts
        ).strip()

    finally:
        document.close()