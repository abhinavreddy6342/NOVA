from pathlib import Path
from typing import Any, Dict, List, Optional

import pymupdf
import pytesseract
from PIL import Image
from docx import Document


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".docx",
}

DEFAULT_OCR_LANGUAGE = "eng"

TESSERACT_PATH = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# Use the installed Windows Tesseract executable when available.
if Path(TESSERACT_PATH).exists():
    pytesseract.pytesseract.tesseract_cmd = (
        TESSERACT_PATH
    )


# ---------------------------------------------------------------------------
# RESULT MODEL
# ---------------------------------------------------------------------------

class ExtractionResult:
    """
    Standardized result returned by NOVA's document extractor.
    """

    def __init__(
        self,
        file_path: str,
        file_type: str,
        text: str,
        pages: Optional[List[Dict[str, Any]]] = None,
        used_ocr: bool = False,
    ) -> None:
        self.file_path = file_path
        self.file_type = file_type
        self.text = text
        self.pages = pages or []
        self.used_ocr = used_ocr

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "file_type": self.file_type,
            "text": self.text,
            "pages": self.pages,
            "used_ocr": self.used_ocr,
            "character_count": len(self.text),
        }


# ---------------------------------------------------------------------------
# DOCUMENT EXTRACTOR
# ---------------------------------------------------------------------------

class DocumentExtractor:
    """
    Local document extraction engine for NOVA.

    Supported:
    - PDF
    - TXT
    - DOCX

    PDF processing:
    1. Native text extraction with PyMuPDF.
    2. Local Tesseract OCR fallback for scanned/image PDFs.
    """

    def __init__(
        self,
        ocr_language: str = DEFAULT_OCR_LANGUAGE,
    ) -> None:
        self.ocr_language = ocr_language

    # -----------------------------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------------------------

    def validate_file(
        self,
        file_path: str,
    ) -> Path:
        """
        Validate and return a supported document path.
        """

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Document does not exist: {file_path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Document path is not a file: {file_path}"
            )

        extension = path.suffix.lower()

        if extension not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported document type: {extension}. "
                f"Supported types: "
                f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        return path

    # -----------------------------------------------------------------------
    # TXT
    # -----------------------------------------------------------------------

    def extract_txt(
        self,
        path: Path,
    ) -> ExtractionResult:
        """
        Extract text from a plain-text file.
        """

        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        return ExtractionResult(
            file_path=str(path),
            file_type="txt",
            text=text,
            pages=[
                {
                    "page": 1,
                    "text": text,
                }
            ],
            used_ocr=False,
        )

    # -----------------------------------------------------------------------
    # DOCX
    # -----------------------------------------------------------------------

    def extract_docx(
        self,
        path: Path,
    ) -> ExtractionResult:
        """
        Extract paragraphs and tables from DOCX.
        """

        document = Document(
            str(path)
        )

        blocks: List[str] = []

        # Paragraphs
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()

            if text:
                blocks.append(text)

        # Tables
        for table_index, table in enumerate(
            document.tables,
            start=1,
        ):
            blocks.append(
                f"[TABLE {table_index}]"
            )

            for row in table.rows:
                cells = [
                    cell.text.strip()
                    for cell in row.cells
                ]

                blocks.append(
                    " | ".join(cells)
                )

        text = "\n".join(
            blocks
        ).strip()

        return ExtractionResult(
            file_path=str(path),
            file_type="docx",
            text=text,
            pages=[
                {
                    "page": 1,
                    "text": text,
                }
            ],
            used_ocr=False,
        )

    # -----------------------------------------------------------------------
    # PDF NATIVE EXTRACTION
    # -----------------------------------------------------------------------

    def _extract_pdf_native(
        self,
        document: pymupdf.Document,
    ) -> List[Dict[str, Any]]:
        """
        Extract text page-by-page using PyMuPDF.
        """

        pages: List[Dict[str, Any]] = []

        for page_number, page in enumerate(
            document,
            start=1,
        ):
            text = page.get_text(
                "text"
            ).strip()

            pages.append(
                {
                    "page": page_number,
                    "text": text,
                }
            )

        return pages

    # -----------------------------------------------------------------------
    # PDF OCR
    # -----------------------------------------------------------------------

    def _ocr_pdf_page(
        self,
        page: pymupdf.Page,
    ) -> str:
        """
        Render one PDF page and process it with local Tesseract OCR.
        """

        # Render at 2x resolution for better OCR quality.
        matrix = pymupdf.Matrix(
            2.0,
            2.0,
        )

        pixmap = page.get_pixmap(
            matrix=matrix,
            alpha=False,
        )

        image = Image.frombytes(
            "RGB",
            (
                pixmap.width,
                pixmap.height,
            ),
            pixmap.samples,
        )

        text = pytesseract.image_to_string(
            image,
            lang=self.ocr_language,
        )

        return text.strip()

    def _extract_pdf_ocr(
        self,
        document: pymupdf.Document,
    ) -> List[Dict[str, Any]]:
        """
        OCR every page in a PDF using local Tesseract.
        """

        pages: List[Dict[str, Any]] = []

        for page_number, page in enumerate(
            document,
            start=1,
        ):
            text = self._ocr_pdf_page(
                page
            )

            pages.append(
                {
                    "page": page_number,
                    "text": text,
                }
            )

        return pages

    # -----------------------------------------------------------------------
    # PDF
    # -----------------------------------------------------------------------

    def extract_pdf(
        self,
        path: Path,
    ) -> ExtractionResult:
        """
        Extract PDF text.

        Native extraction is preferred.
        OCR is used when native extraction contains
        little or no meaningful text.
        """

        document = pymupdf.open(
            str(path)
        )

        try:
            native_pages = (
                self._extract_pdf_native(
                    document
                )
            )

            native_text = "\n".join(
                page["text"]
                for page in native_pages
            ).strip()

            # ---------------------------------------------------------------
            # Native text is sufficient.
            # ---------------------------------------------------------------

            if len(native_text) >= 20:
                return ExtractionResult(
                    file_path=str(path),
                    file_type="pdf",
                    text=native_text,
                    pages=native_pages,
                    used_ocr=False,
                )

            # ---------------------------------------------------------------
            # Fallback to OCR.
            # ---------------------------------------------------------------

            ocr_pages = (
                self._extract_pdf_ocr(
                    document
                )
            )

            ocr_text = "\n".join(
                page["text"]
                for page in ocr_pages
            ).strip()

            return ExtractionResult(
                file_path=str(path),
                file_type="pdf",
                text=ocr_text,
                pages=ocr_pages,
                used_ocr=True,
            )

        finally:
            document.close()

    # -----------------------------------------------------------------------
    # UNIVERSAL EXTRACTION
    # -----------------------------------------------------------------------

    def extract(
        self,
        file_path: str,
    ) -> ExtractionResult:
        """
        Extract content from any supported local document.
        """

        path = self.validate_file(
            file_path
        )

        extension = path.suffix.lower()

        if extension == ".pdf":
            return self.extract_pdf(
                path
            )

        if extension == ".txt":
            return self.extract_txt(
                path
            )

        if extension == ".docx":
            return self.extract_docx(
                path
            )

        # This should be unreachable because validate_file()
        # already checks the extension.
        raise ValueError(
            f"No extractor available for {extension}"
        )


# ---------------------------------------------------------------------------
# SHARED EXTRACTOR
# ---------------------------------------------------------------------------

document_extractor = DocumentExtractor()


def extract_document(
    file_path: str,
) -> ExtractionResult:
    """
    Convenience function for NOVA document extraction.
    """

    return document_extractor.extract(
        file_path
    )