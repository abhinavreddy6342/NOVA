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
    ".png",
    ".jpg",
    ".jpeg",
}

DEFAULT_OCR_LANGUAGE = "eng"

TESSERACT_PATH = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

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
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.file_path = file_path
        self.file_type = file_type
        self.text = text
        self.pages = pages or []
        self.used_ocr = used_ocr
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "file_type": self.file_type,
            "text": self.text,
            "pages": self.pages,
            "used_ocr": self.used_ocr,
            "metadata": self.metadata,
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
    1. Open with PyMuPDF.
    2. Extract native text page-by-page.
    3. Determine whether enough meaningful text was extracted.
    4. Use local Tesseract OCR only where native extraction is insufficient.
    5. Preserve page-level text for downstream agent reasoning.

    DOCX processing:
    - Paragraphs
    - Tables
    - Basic document properties

    TXT processing:
    - UTF-8 / UTF-8-SIG text
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

        if not file_path or not str(file_path).strip():
            raise ValueError(
                "Document path cannot be empty."
            )

        path = Path(
            str(file_path).strip()
        ).resolve()

        if not path.exists():
            raise FileNotFoundError(
                f"Document does not exist: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Document path is not a file: {path}"
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

        try:
            text = path.read_text(
                encoding="utf-8-sig",
                errors="replace",
            )
        except OSError as exc:
            raise RuntimeError(
                f"Could not read TXT file: {path}"
            ) from exc

        text = text.strip()

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
            metadata={
                "filename": path.name,
                "extension": ".txt",
            },
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

        try:
            document = Document(
                str(path)
            )
        except Exception as exc:
            raise RuntimeError(
                f"Could not open DOCX file: {path}"
            ) from exc

        blocks: List[str] = []

        # ---------------------------------------------------------------
        # Paragraphs
        # ---------------------------------------------------------------

        for paragraph in document.paragraphs:

            text = (
                paragraph.text
                or ""
            ).strip()

            if text:
                blocks.append(
                    text
                )

        # ---------------------------------------------------------------
        # Tables
        # ---------------------------------------------------------------

        for table_index, table in enumerate(
            document.tables,
            start=1,
        ):

            blocks.append(
                f"[TABLE {table_index}]"
            )

            for row in table.rows:

                cells = []

                for cell in row.cells:

                    cell_text = (
                        cell.text
                        or ""
                    ).strip()

                    cells.append(
                        cell_text
                    )

                # Preserve empty cells without losing
                # table column structure.
                blocks.append(
                    " | ".join(
                        cells
                    )
                )

        text = "\n".join(
            blocks
        ).strip()

        # ---------------------------------------------------------------
        # Basic metadata
        # ---------------------------------------------------------------

        metadata: Dict[str, Any] = {
            "filename": path.name,
            "extension": ".docx",
            "paragraph_count": len(
                document.paragraphs
            ),
            "table_count": len(
                document.tables
            ),
        }

        try:

            properties = (
                document.core_properties
            )

            metadata.update(
                {
                    "title": (
                        properties.title
                        or ""
                    ),
                    "subject": (
                        properties.subject
                        or ""
                    ),
                    "author": (
                        properties.author
                        or ""
                    ),
                }
            )

        except Exception:
            pass

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
            metadata=metadata,
        )

    # -----------------------------------------------------------------------
    # PDF HELPERS
    # -----------------------------------------------------------------------

    @staticmethod
    def _meaningful_text_length(
        text: str,
    ) -> int:
        """
        Count meaningful non-whitespace characters.

        This avoids deciding that a page contains useful text merely
        because it contains a few isolated control/layout characters.
        """

        if not text:
            return 0

        return len(
            " ".join(
                str(text).split()
            )
        )

    @staticmethod
    def _clean_extracted_text(
        text: str,
    ) -> str:
        """
        Normalize common PDF extraction whitespace.
        """

        if not text:
            return ""

        lines = []

        for line in str(
            text
        ).splitlines():

            cleaned = " ".join(
                line.split()
            ).strip()

            if cleaned:
                lines.append(
                    cleaned
                )

        return "\n".join(
            lines
        ).strip()

    # -----------------------------------------------------------------------
    # PDF NATIVE EXTRACTION
    # -----------------------------------------------------------------------

    def _extract_pdf_native(
        self,
        document: pymupdf.Document,
    ) -> List[Dict[str, Any]]:
        """
        Extract text page-by-page using PyMuPDF.

        Each page is isolated so the agent can see exactly where
        information came from.
        """

        pages: List[
            Dict[str, Any]
        ] = []

        page_count = len(
            document
        )

        for page_number in range(
            page_count
        ):

            try:

                page = document.load_page(
                    page_number
                )

                raw_text = page.get_text(
                    "text"
                )

                text = self._clean_extracted_text(
                    raw_text
                )

                pages.append(
                    {
                        "page": page_number + 1,
                        "text": text,
                        "character_count": len(
                            text
                        ),
                    }
                )

            except Exception as exc:

                pages.append(
                    {
                        "page": page_number + 1,
                        "text": "",
                        "character_count": 0,
                        "error": (
                            f"Native extraction failed: "
                            f"{type(exc).__name__}"
                        ),
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

        OCR is deliberately performed one page at a time so that a
        problematic page cannot destroy the complete PDF extraction.
        """

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

        try:

            text = pytesseract.image_to_string(
                image,
                lang=self.ocr_language,
            )

        finally:

            try:
                image.close()
            except Exception:
                pass

        return self._clean_extracted_text(
            text
        )

    def _extract_pdf_ocr(
        self,
        document: pymupdf.Document,
        only_empty_pages: bool = True,
        native_pages: Optional[
            List[Dict[str, Any]]
        ] = None,
    ) -> List[Dict[str, Any]]:
        """
        OCR PDF pages locally.

        When only_empty_pages=True, native page text is retained for
        pages that already extracted successfully and OCR is applied
        only to pages that have little/no native text.
        """

        pages: List[
            Dict[str, Any]
        ] = []

        page_count = len(
            document
        )

        for page_number in range(
            page_count
        ):

            existing_text = ""

            if (
                native_pages
                and page_number
                < len(native_pages)
            ):
                existing_text = str(
                    native_pages[
                        page_number
                    ].get(
                        "text",
                        "",
                    )
                ).strip()

            should_ocr = True

            if only_empty_pages:

                should_ocr = (
                    self._meaningful_text_length(
                        existing_text
                    )
                    < 20
                )

            if not should_ocr:

                pages.append(
                    {
                        "page": page_number + 1,
                        "text": existing_text,
                        "character_count": len(
                            existing_text
                        ),
                        "ocr": False,
                    }
                )

                continue

            try:

                page = document.load_page(
                    page_number
                )

                text = self._ocr_pdf_page(
                    page
                )

                # If OCR produces nothing but native text exists,
                # retain the native extraction.
                if (
                    not text
                    and existing_text
                ):
                    text = existing_text

                pages.append(
                    {
                        "page": page_number + 1,
                        "text": text,
                        "character_count": len(
                            text
                        ),
                        "ocr": True,
                    }
                )

            except Exception as exc:

                # Preserve any useful native text instead of failing
                # the complete document.
                pages.append(
                    {
                        "page": page_number + 1,
                        "text": existing_text,
                        "character_count": len(
                            existing_text
                        ),
                        "ocr": True,
                        "ocr_error": (
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
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
        Extract PDF text robustly.

        Native extraction is always attempted first.

        OCR behavior:
        - If native extraction is good, return it directly.
        - If some pages have no useful text, OCR only those pages.
        - If the complete native extraction is effectively empty,
          OCR the complete document.
        """

        try:

            document = pymupdf.open(
                str(path)
            )

        except Exception as exc:

            raise RuntimeError(
                f"Could not open PDF file: {path}"
            ) from exc

        try:

            page_count = len(
                document
            )

            # -----------------------------------------------------------
            # Metadata
            # -----------------------------------------------------------

            metadata: Dict[str, Any] = {
                "filename": path.name,
                "extension": ".pdf",
                "page_count": page_count,
            }

            try:

                pdf_metadata = (
                    document.metadata
                    or {}
                )

                metadata.update(
                    {
                        "title": (
                            pdf_metadata.get(
                                "title"
                            )
                            or ""
                        ),
                        "author": (
                            pdf_metadata.get(
                                "author"
                            )
                            or ""
                        ),
                        "subject": (
                            pdf_metadata.get(
                                "subject"
                            )
                            or ""
                        ),
                        "creator": (
                            pdf_metadata.get(
                                "creator"
                            )
                            or ""
                        ),
                        "producer": (
                            pdf_metadata.get(
                                "producer"
                            )
                            or ""
                        ),
                    }
                )

            except Exception:
                pass

            # -----------------------------------------------------------
            # Native extraction
            # -----------------------------------------------------------

            native_pages = (
                self._extract_pdf_native(
                    document
                )
            )

            native_text = "\n\n".join(
                (
                    f"[PAGE {page['page']}]\n"
                    f"{page.get('text', '')}"
                )
                for page in native_pages
                if str(
                    page.get(
                        "text",
                        "",
                    )
                ).strip()
            ).strip()

            total_native_chars = sum(
                int(
                    page.get(
                        "character_count",
                        0,
                    )
                    or 0
                )
                for page in native_pages
            )

            pages_with_native_text = sum(
                1
                for page in native_pages
                if self._meaningful_text_length(
                    str(
                        page.get(
                            "text",
                            "",
                        )
                    )
                ) >= 20
            )

            # -----------------------------------------------------------
            # Native extraction is sufficient
            # -----------------------------------------------------------

            if (
                total_native_chars >= 80
                and pages_with_native_text >= max(
                    1,
                    min(
                        page_count,
                        2,
                    ),
                )
            ):

                return ExtractionResult(
                    file_path=str(path),
                    file_type="pdf",
                    text=native_text,
                    pages=native_pages,
                    used_ocr=False,
                    metadata=metadata,
                )

            # -----------------------------------------------------------
            # OCR fallback
            # -----------------------------------------------------------

            ocr_pages = (
                self._extract_pdf_ocr(
                    document,
                    only_empty_pages=True,
                    native_pages=native_pages,
                )
            )

            ocr_text = "\n\n".join(
                (
                    f"[PAGE {page['page']}]\n"
                    f"{page.get('text', '')}"
                )
                for page in ocr_pages
                if str(
                    page.get(
                        "text",
                        "",
                    )
                ).strip()
            ).strip()

            ocr_char_count = len(
                ocr_text
            )

            # Prefer whichever extraction actually produced more
            # meaningful content.
            if (
                ocr_char_count
                >= total_native_chars
            ):

                final_pages = ocr_pages
                final_text = ocr_text
                used_ocr = True

            else:

                final_pages = native_pages
                final_text = native_text
                used_ocr = False

            # -----------------------------------------------------------
            # No content at all
            # -----------------------------------------------------------

            if not final_text.strip():

                raise RuntimeError(
                    "PDF extraction produced no readable text. "
                    "The PDF may contain unsupported content, "
                    "encrypted content, or images that Tesseract "
                    "could not recognize."
                )

            metadata[
                "native_character_count"
            ] = total_native_chars

            metadata[
                "ocr_character_count"
            ] = ocr_char_count

            metadata[
                "native_pages_with_text"
            ] = pages_with_native_text

            return ExtractionResult(
                file_path=str(path),
                file_type="pdf",
                text=final_text,
                pages=final_pages,
                used_ocr=used_ocr,
                metadata=metadata,
            )

        finally:

            try:
                document.close()
            except Exception:
                pass

    def extract_image(
        self,
        path: Path,
    ) -> ExtractionResult:
        """
        Extract readable text and metadata from image files using local OCR.
        """
        text = ""
        used_ocr = False
        width, height, format_name = 0, 0, path.suffix.upper().lstrip(".")

        try:
            with Image.open(path) as img:
                width, height = img.size
                format_name = img.format or format_name
                try:
                    ocr_text = pytesseract.image_to_string(img, lang=self.ocr_language).strip()
                    if ocr_text:
                        text = ocr_text
                        used_ocr = True
                except Exception:
                    pass
        except Exception as exc:
            raise RuntimeError(
                f"Could not open image file: {path}"
            ) from exc

        if not text:
            text = (
                f"Image file '{path.name}' ({format_name}, {width}x{height} pixels). "
                "No readable text recognized by OCR."
            )

        return ExtractionResult(
            file_path=str(path),
            file_type="image",
            text=text,
            pages=[
                {
                    "page": 1,
                    "text": text,
                }
            ],
            used_ocr=used_ocr,
            metadata={
                "filename": path.name,
                "extension": path.suffix.lower(),
                "width": width,
                "height": height,
                "format": format_name,
            },
        )

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

        if extension in {".png", ".jpg", ".jpeg"}:

            return self.extract_image(
                path
            )

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