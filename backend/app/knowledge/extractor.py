from io import BytesIO
from pathlib import Path
from typing import List

import pymupdf
import pymupdf.layout
import pytesseract
from docx import Document
from PIL import Image


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".docx",
}


# ---------------------------------------------------------------------------
# TESSERACT
# ---------------------------------------------------------------------------

TESSERACT_PATH = Path(
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

if TESSERACT_PATH.exists():
    pytesseract.pytesseract.tesseract_cmd = str(
        TESSERACT_PATH
    )


# ---------------------------------------------------------------------------
# PUBLIC ENTRY POINT
# ---------------------------------------------------------------------------

def extract_text(
    file_path: str,
) -> str:
    """
    Extract text from supported document formats.

    PDF strategy:
    1. Use PyMuPDF Layout for layout-aware extraction.
    2. Preserve page boundaries.
    3. Add detected table data when available.
    4. Use normal native extraction as a fallback.
    5. Use local OCR only when the PDF is genuinely unreadable.
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


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

def extract_docx(
    path: Path,
) -> str:
    """
    Extract paragraphs and tables from a DOCX document.
    """

    document = Document(path)

    parts: List[str] = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()

        if text:
            parts.append(text)

    for table_index, table in enumerate(
        document.tables,
        start=1,
    ):
        parts.append(
            f"[Table {table_index}]"
        )

        for row in table.rows:
            cells = [
                cell.text.strip()
                for cell in row.cells
            ]

            if any(cells):
                parts.append(
                    " | ".join(cells)
                )

    return "\n".join(parts).strip()


# ---------------------------------------------------------------------------
# PYMuPDF LAYOUT
# ---------------------------------------------------------------------------

def _extract_layout_pdf_text(
    document: pymupdf.Document,
) -> str:
    """
    Extract PDF text using PyMuPDF Layout.

    The layout package improves ordering of text blocks,
    especially in documents containing columns and tables.
    """

    page_parts: List[str] = []

    for page_number, page in enumerate(
        document,
        start=1,
    ):
        try:
            # PyMuPDF Layout adds layout-aware text extraction
            # behavior to the existing Page object.
            text = page.get_text(
                "text"
            ).strip()

            if text:
                page_parts.append(
                    f"[Page {page_number}]\n{text}"
                )

        except Exception as exc:
            print(
                f"Layout extraction failed on "
                f"page {page_number}: {exc}"
            )

    return "\n\n".join(
        page_parts
    ).strip()


# ---------------------------------------------------------------------------
# NORMAL NATIVE PDF TEXT
# ---------------------------------------------------------------------------

def _extract_native_pdf_text(
    document: pymupdf.Document,
) -> str:
    """
    Extract normal native PDF text page by page.
    """

    page_parts: List[str] = []

    for page_number, page in enumerate(
        document,
        start=1,
    ):
        try:
            text = page.get_text(
                "text"
            ).strip()
        except Exception:
            text = ""

        if text:
            page_parts.append(
                f"[Page {page_number}]\n{text}"
            )

    return "\n\n".join(
        page_parts
    ).strip()


# ---------------------------------------------------------------------------
# TABLE EXTRACTION
# ---------------------------------------------------------------------------

def _extract_pdf_tables(
    document: pymupdf.Document,
) -> str:
    """
    Extract tables detected by PyMuPDF.

    Table information is preserved separately so that
    downstream RAG can use row/cell relationships.
    """

    page_parts: List[str] = []

    for page_number, page in enumerate(
        document,
        start=1,
    ):
        try:
            table_result = page.find_tables()

            tables = getattr(
                table_result,
                "tables",
                [],
            )

            if not tables:
                continue

            page_parts.append(
                f"[Page {page_number} Tables]"
            )

            for table_index, table in enumerate(
                tables,
                start=1,
            ):
                try:
                    rows = table.extract()
                except Exception as exc:
                    print(
                        f"Table extraction failed on "
                        f"page {page_number}, "
                        f"table {table_index}: {exc}"
                    )
                    continue

                if not rows:
                    continue

                page_parts.append(
                    f"[Table {table_index}]"
                )

                for row in rows:
                    if not row:
                        continue

                    cells: List[str] = []

                    for cell in row:
                        if cell is None:
                            cells.append("")
                        else:
                            cells.append(
                                str(
                                    cell
                                ).strip()
                            )

                    if any(cells):
                        page_parts.append(
                            " | ".join(
                                cells
                            )
                        )

        except Exception as exc:
            print(
                f"Table detection failed on "
                f"page {page_number}: {exc}"
            )

    return "\n".join(
        page_parts
    ).strip()


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

def _extract_pdf_ocr(
    document: pymupdf.Document,
) -> str:
    """
    Render PDF pages and run local Tesseract OCR.
    """

    if not TESSERACT_PATH.exists():
        raise RuntimeError(
            "Tesseract was not found at: "
            f"{TESSERACT_PATH}"
        )

    ocr_parts: List[str] = []

    for page_number, page in enumerate(
        document,
        start=1,
    ):
        print(
            f"OCR processing page "
            f"{page_number}/"
            f"{document.page_count}..."
        )

        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(
                3,
                3,
            ),
            colorspace=pymupdf.csRGB,
            alpha=False,
        )

        png_bytes = pixmap.tobytes(
            "png"
        )

        image = Image.open(
            BytesIO(
                png_bytes
            )
        ).convert(
            "RGB"
        )

        text = pytesseract.image_to_string(
            image,
            lang="eng",
            config="--psm 3",
        ).strip()

        if text:
            ocr_parts.append(
                f"[Page {page_number}]\n{text}"
            )

    return "\n\n".join(
        ocr_parts
    ).strip()


# ---------------------------------------------------------------------------
# CONTENT COMBINATION
# ---------------------------------------------------------------------------

def _combine_pdf_content(
    layout_text: str,
    native_text: str,
    table_text: str,
) -> str:
    """
    Combine the best available PDF representations.

    Layout-aware text is preferred, with native text used
    as a fallback when layout extraction is unavailable.
    """

    primary_text = (
        layout_text.strip()
        if layout_text.strip()
        else native_text.strip()
    )

    if primary_text and table_text:
        return (
            f"{primary_text}\n\n"
            "========== STRUCTURED TABLE DATA ==========\n\n"
            f"{table_text}"
        ).strip()

    if primary_text:
        return primary_text

    return table_text.strip()


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def extract_pdf(
    path: Path,
) -> str:
    """
    Extract PDF using layout-aware text, native text,
    table extraction, and local OCR fallback.
    """

    document = pymupdf.open(
        str(path)
    )

    try:
        # ---------------------------------------------------------------
        # Layout-aware extraction
        # ---------------------------------------------------------------

        layout_text = _extract_layout_pdf_text(
            document
        )

        # ---------------------------------------------------------------
        # Native extraction
        # ---------------------------------------------------------------

        native_text = _extract_native_pdf_text(
            document
        )

        # ---------------------------------------------------------------
        # Structured tables
        # ---------------------------------------------------------------

        table_text = _extract_pdf_tables(
            document
        )

        # ---------------------------------------------------------------
        # Combine
        # ---------------------------------------------------------------

        combined_text = _combine_pdf_content(
            layout_text=layout_text,
            native_text=native_text,
            table_text=table_text,
        )

        # ---------------------------------------------------------------
        # Use layout/native/table extraction
        # ---------------------------------------------------------------

        if len(combined_text.strip()) >= 50:
            print(
                "PDF layout/native extraction succeeded."
            )

            if table_text:
                print(
                    "Structured table extraction also succeeded."
                )

            return combined_text

        # ---------------------------------------------------------------
        # OCR fallback
        # ---------------------------------------------------------------

        print(
            "PDF layout/native extraction returned "
            "little/no usable text."
        )

        print(
            "Starting local OCR fallback..."
        )

        return _extract_pdf_ocr(
            document
        )

    finally:
        document.close()