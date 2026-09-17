from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path
from typing import Any, Dict, List, Optional

import pymupdf
import pytesseract
from PIL import Image
from docx import Document
from openpyxl import load_workbook


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".docx",
    ".csv",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}

DEFAULT_OCR_LANGUAGE = "eng"

TESSERACT_PATH = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

if Path(
    TESSERACT_PATH
).exists():
    pytesseract.pytesseract.tesseract_cmd = (
        TESSERACT_PATH
    )


# ---------------------------------------------------------------------------
# RESULT MODEL
# ---------------------------------------------------------------------------

class ExtractionResult:
    """
    Standardized result returned by NOVA's local document extraction engine.
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
    Local-only content extraction engine for NOVA.

    Supported:
    - PDF
    - TXT
    - DOCX
    - CSV
    - XLSX
    - PNG
    - JPG
    - JPEG
    - WEBP

    PDF:
    - Native extraction first.
    - Page-level extraction.
    - Local Tesseract OCR fallback for weak pages.

    DOCX:
    - Paragraphs.
    - Tables.
    - Basic metadata.

    CSV:
    - Structured row/column extraction.

    XLSX:
    - Workbook/sheet/row/cell extraction.

    Images:
    - Local OCR.
    - Image metadata.
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
        Validate and return a supported local file path.

        Storage ownership and filesystem authorization are handled by the
        calling NOVA service. This extractor validates that the supplied
        path is a real supported file.
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
    # CHECKSUM
    # -----------------------------------------------------------------------

    @staticmethod
    def calculate_sha256(
        path: Path,
    ) -> str:
        """
        Calculate a real SHA-256 checksum for the local source file.
        """

        digest = hashlib.sha256()

        try:
            with path.open(
                "rb"
            ) as handle:
                for block in iter(
                    lambda: handle.read(
                        1024 * 1024
                    ),
                    b"",
                ):
                    digest.update(block)

        except OSError as exc:
            raise RuntimeError(
                f"Could not calculate file checksum: {path}"
            ) from exc

        return digest.hexdigest()

    def _base_metadata(
        self,
        path: Path,
    ) -> Dict[str, Any]:
        """
        Common real filesystem metadata shared by every extraction result.
        """

        try:
            stat = path.stat()
        except OSError as exc:
            raise RuntimeError(
                f"Could not read file metadata: {path}"
            ) from exc

        return {
            "filename": path.name,
            "extension": path.suffix.lower(),
            "size": int(
                stat.st_size
            ),
            "size_bytes": int(
                stat.st_size
            ),
            "modified_at": (
                self._iso_timestamp(
                    stat.st_mtime
                )
            ),
            "sha256": self.calculate_sha256(
                path
            ),
        }

    @staticmethod
    def _iso_timestamp(
        timestamp: float,
    ) -> str:
        from datetime import (
            datetime,
            timezone,
        )

        return datetime.fromtimestamp(
            timestamp,
            timezone.utc,
        ).isoformat()

    # -----------------------------------------------------------------------
    # COMMON TEXT HELPERS
    # -----------------------------------------------------------------------

    @staticmethod
    def _clean_text(
        text: str,
    ) -> str:
        """
        Normalize repeated whitespace while preserving logical lines.
        """

        if not text:
            return ""

        lines: List[str] = []

        for line in str(text).splitlines():
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

    @staticmethod
    def _meaningful_text_length(
        text: str,
    ) -> int:
        """
        Count meaningful non-whitespace characters.
        """

        if not text:
            return 0

        return len(
            " ".join(
                str(text).split()
            )
        )

    # -----------------------------------------------------------------------
    # TXT
    # -----------------------------------------------------------------------

    def extract_txt(
        self,
        path: Path,
    ) -> ExtractionResult:
        try:
            text = path.read_text(
                encoding="utf-8-sig",
                errors="replace",
            )

        except OSError as exc:
            raise RuntimeError(
                f"Could not read TXT file: {path}"
            ) from exc

        text = self._clean_text(
            text
        )

        metadata = self._base_metadata(
            path
        )

        metadata["line_count"] = len(
            text.splitlines()
        ) if text else 0

        return ExtractionResult(
            file_path=str(path),
            file_type="txt",
            text=text,
            pages=[
                {
                    "page": 1,
                    "text": text,
                    "character_count": len(text),
                }
            ],
            used_ocr=False,
            metadata=metadata,
        )

    # -----------------------------------------------------------------------
    # DOCX
    # -----------------------------------------------------------------------

    def extract_docx(
        self,
        path: Path,
    ) -> ExtractionResult:
        try:
            document = Document(
                str(path)
            )

        except Exception as exc:
            raise RuntimeError(
                f"Could not open DOCX file: {path}"
            ) from exc

        blocks: List[str] = []

        for paragraph in document.paragraphs:
            text = (
                paragraph.text
                or ""
            ).strip()

            if text:
                blocks.append(
                    text
                )

        for table_index, table in enumerate(
            document.tables,
            start=1,
        ):
            blocks.append(
                f"[TABLE {table_index}]"
            )

            for row in table.rows:
                cells: List[str] = []

                for cell in row.cells:
                    cell_text = (
                        cell.text
                        or ""
                    ).strip()

                    cells.append(
                        cell_text
                    )

                blocks.append(
                    " | ".join(cells)
                )

        text = self._clean_text(
            "\n".join(blocks)
        )

        metadata = self._base_metadata(
            path
        )

        metadata.update(
            {
                "paragraph_count": len(
                    document.paragraphs
                ),
                "table_count": len(
                    document.tables
                ),
            }
        )

        try:
            properties = document.core_properties

            metadata.update(
                {
                    "title": properties.title or "",
                    "subject": properties.subject or "",
                    "author": properties.author or "",
                    "keywords": properties.keywords or "",
                    "comments": properties.comments or "",
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
                    "character_count": len(text),
                }
            ],
            used_ocr=False,
            metadata=metadata,
        )

    # -----------------------------------------------------------------------
    # CSV
    # -----------------------------------------------------------------------

    def extract_csv(
        self,
        path: Path,
    ) -> ExtractionResult:
        try:
            raw = path.read_text(
                encoding="utf-8-sig",
                errors="replace",
            )

        except OSError as exc:
            raise RuntimeError(
                f"Could not read CSV file: {path}"
            ) from exc

        metadata = self._base_metadata(
            path
        )

        if not raw.strip():
            metadata.update(
                {
                    "row_count": 0,
                    "column_count": 0,
                }
            )

            return ExtractionResult(
                file_path=str(path),
                file_type="csv",
                text="",
                pages=[
                    {
                        "page": 1,
                        "text": "",
                        "character_count": 0,
                    }
                ],
                used_ocr=False,
                metadata=metadata,
            )

        try:
            sample = raw[:8192]

            dialect = csv.Sniffer().sniff(
                sample
            )

        except csv.Error:
            dialect = csv.excel

        try:
            rows = list(
                csv.reader(
                    io.StringIO(raw),
                    dialect,
                )
            )

        except Exception as exc:
            raise RuntimeError(
                f"Could not parse CSV file: {path}"
            ) from exc

        column_count = max(
            (
                len(row)
                for row in rows
            ),
            default=0,
        )

        blocks: List[str] = []

        for row_number, row in enumerate(
            rows,
            start=1,
        ):
            values = [
                str(value).strip()
                for value in row
            ]

            blocks.append(
                f"[ROW {row_number}] "
                + " | ".join(values)
            )

        text = self._clean_text(
            "\n".join(blocks)
        )

        metadata.update(
            {
                "row_count": len(rows),
                "column_count": column_count,
            }
        )

        return ExtractionResult(
            file_path=str(path),
            file_type="csv",
            text=text,
            pages=[
                {
                    "page": 1,
                    "text": text,
                    "character_count": len(text),
                }
            ],
            used_ocr=False,
            metadata=metadata,
        )

    # -----------------------------------------------------------------------
    # XLSX
    # -----------------------------------------------------------------------

    def extract_xlsx(
        self,
        path: Path,
    ) -> ExtractionResult:
        try:
            workbook = load_workbook(
                filename=str(path),
                read_only=True,
                data_only=True,
            )

        except Exception as exc:
            raise RuntimeError(
                f"Could not open XLSX file: {path}"
            ) from exc

        pages: List[
            Dict[str, Any]
        ] = []

        document_blocks: List[str] = []

        total_rows = 0
        total_columns = 0

        try:
            for sheet_index, worksheet in enumerate(
                workbook.worksheets,
                start=1,
            ):
                sheet_blocks: List[str] = []

                sheet_blocks.append(
                    f"[SHEET {sheet_index}: {worksheet.title}]"
                )

                sheet_rows = 0
                sheet_columns = 0

                for row_number, row in enumerate(
                    worksheet.iter_rows(
                        values_only=True
                    ),
                    start=1,
                ):
                    values: List[str] = []

                    for value in row:
                        if value is None:
                            values.append("")

                        else:
                            values.append(
                                str(
                                    value
                                ).strip()
                            )

                    while (
                        values
                        and values[-1] == ""
                    ):
                        values.pop()

                    if not values:
                        continue

                    sheet_rows += 1

                    sheet_columns = max(
                        sheet_columns,
                        len(values),
                    )

                    sheet_blocks.append(
                        f"[ROW {row_number}] "
                        + " | ".join(values)
                    )

                sheet_text = self._clean_text(
                    "\n".join(sheet_blocks)
                )

                pages.append(
                    {
                        "page": sheet_index,
                        "sheet": worksheet.title,
                        "text": sheet_text,
                        "character_count": len(
                            sheet_text
                        ),
                        "row_count": sheet_rows,
                        "column_count": sheet_columns,
                    }
                )

                if sheet_text:
                    document_blocks.append(
                        sheet_text
                    )

                total_rows += sheet_rows

                total_columns = max(
                    total_columns,
                    sheet_columns,
                )

        finally:
            try:
                workbook.close()

            except Exception:
                pass

        text = "\n\n".join(
            block
            for block in document_blocks
            if block
        ).strip()

        metadata = self._base_metadata(
            path
        )

        metadata.update(
            {
                "sheet_count": len(pages),
                "row_count": total_rows,
                "column_count": total_columns,
            }
        )

        return ExtractionResult(
            file_path=str(path),
            file_type="xlsx",
            text=text,
            pages=pages,
            used_ocr=False,
            metadata=metadata,
        )

    # -----------------------------------------------------------------------
    # PDF NATIVE EXTRACTION
    # -----------------------------------------------------------------------

    def _extract_pdf_native(
        self,
        document: pymupdf.Document,
    ) -> List[Dict[str, Any]]:
        pages: List[
            Dict[str, Any]
        ] = []

        for page_number in range(
            len(document)
        ):
            try:
                page = document.load_page(
                    page_number
                )

                raw_text = page.get_text(
                    "text"
                )

                text = self._clean_text(
                    raw_text
                )

                pages.append(
                    {
                        "page": page_number + 1,
                        "text": text,
                        "character_count": len(text),
                        "ocr": False,
                    }
                )

            except Exception as exc:
                pages.append(
                    {
                        "page": page_number + 1,
                        "text": "",
                        "character_count": 0,
                        "ocr": False,
                        "error": (
                            "Native extraction failed: "
                            f"{type(exc).__name__}: {exc}"
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

        return self._clean_text(
            text
        )

    def _extract_pdf_ocr(
        self,
        document: pymupdf.Document,
        only_weak_pages: bool = True,
        native_pages: Optional[
            List[Dict[str, Any]]
        ] = None,
    ) -> List[Dict[str, Any]]:
        pages: List[
            Dict[str, Any]
        ] = []

        for page_number in range(
            len(document)
        ):
            existing_text = ""

            if (
                native_pages
                and page_number < len(
                    native_pages
                )
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

            if only_weak_pages:
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

                ocr_text = self._ocr_pdf_page(
                    page
                )

                if not ocr_text and existing_text:
                    ocr_text = existing_text

                pages.append(
                    {
                        "page": page_number + 1,
                        "text": ocr_text,
                        "character_count": len(
                            ocr_text
                        ),
                        "ocr": True,
                    }
                )

            except Exception as exc:
                pages.append(
                    {
                        "page": page_number + 1,
                        "text": existing_text,
                        "character_count": len(
                            existing_text
                        ),
                        "ocr": True,
                        "ocr_error": (
                            f"{type(exc).__name__}: {exc}"
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
        try:
            document = pymupdf.open(
                str(path)
            )

        except Exception as exc:
            raise RuntimeError(
                f"Could not open PDF file: {path}"
            ) from exc

        try:
            page_count = len(document)

            metadata = self._base_metadata(
                path
            )

            metadata.update(
                {
                    "page_count": page_count,
                }
            )

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
                        "format": (
                            pdf_metadata.get(
                                "format"
                            )
                            or ""
                        ),
                    }
                )

            except Exception:
                pass

            native_pages = self._extract_pdf_native(
                document
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
                )
                >= 20
            )

            enough_native_text = (
                total_native_chars >= 80
                and pages_with_native_text
                >= max(
                    1,
                    min(
                        page_count,
                        2,
                    ),
                )
            )

            if enough_native_text:
                metadata.update(
                    {
                        "native_character_count": (
                            total_native_chars
                        ),
                        "native_pages_with_text": (
                            pages_with_native_text
                        ),
                        "extraction_method": "native",
                    }
                )

                return ExtractionResult(
                    file_path=str(path),
                    file_type="pdf",
                    text=native_text,
                    pages=native_pages,
                    used_ocr=False,
                    metadata=metadata,
                )

            ocr_pages = self._extract_pdf_ocr(
                document,
                only_weak_pages=True,
                native_pages=native_pages,
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

            # Prefer OCR only when it actually produced at least as much
            # readable material as native extraction.
            if ocr_char_count >= total_native_chars:
                final_pages = ocr_pages
                final_text = ocr_text
                used_ocr = True
                extraction_method = "ocr"
            else:
                final_pages = native_pages
                final_text = native_text
                used_ocr = False
                extraction_method = "native"

            if not final_text.strip():
                raise RuntimeError(
                    "PDF extraction produced no readable text. "
                    "The PDF may contain unsupported content, "
                    "encrypted content, or images that local OCR "
                    "could not recognize."
                )

            metadata.update(
                {
                    "native_character_count": (
                        total_native_chars
                    ),
                    "ocr_character_count": (
                        ocr_char_count
                    ),
                    "native_pages_with_text": (
                        pages_with_native_text
                    ),
                    "extraction_method": (
                        extraction_method
                    ),
                }
            )

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

    # -----------------------------------------------------------------------
    # IMAGE
    # -----------------------------------------------------------------------

    def extract_image(
        self,
        path: Path,
    ) -> ExtractionResult:
        """
        Extract text from images using local Tesseract OCR.

        Important:
        If OCR finds no readable text, text remains empty. Real image
        metadata is still returned for preview, but synthetic descriptive
        text is never inserted into the knowledge index.
        """

        text = ""
        used_ocr = False

        width = 0
        height = 0

        format_name = (
            path.suffix
            .upper()
            .lstrip(".")
        )

        try:
            with Image.open(
                path
            ) as image:
                width, height = image.size

                format_name = (
                    image.format
                    or format_name
                )

                try:
                    ocr_text = pytesseract.image_to_string(
                        image,
                        lang=self.ocr_language,
                    )

                    ocr_text = self._clean_text(
                        ocr_text
                    )

                    if ocr_text:
                        text = ocr_text
                        used_ocr = True

                except Exception as exc:
                    print(
                        "[NOVA IMAGE OCR] "
                        f"{type(exc).__name__}: {exc}"
                    )

        except Exception as exc:
            raise RuntimeError(
                f"Could not open image file: {path}"
            ) from exc

        metadata = self._base_metadata(
            path
        )

        metadata.update(
            {
                "width": width,
                "height": height,
                "format": format_name,
                "ocr_available": Path(
                    TESSERACT_PATH
                ).exists(),
                "ocr_text_found": bool(text),
            }
        )

        return ExtractionResult(
            file_path=str(path),
            file_type="image",
            text=text,
            pages=[
                {
                    "page": 1,
                    "text": text,
                    "character_count": len(text),
                    "ocr": used_ocr,
                }
            ],
            used_ocr=used_ocr,
            metadata=metadata,
        )

    # -----------------------------------------------------------------------
    # UNIVERSAL EXTRACTION
    # -----------------------------------------------------------------------

    def extract(
        self,
        file_path: str,
    ) -> ExtractionResult:
        """
        Extract supported local content.
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

        if extension == ".csv":
            return self.extract_csv(
                path
            )

        if extension == ".xlsx":
            return self.extract_xlsx(
                path
            )

        if extension in {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        }:
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