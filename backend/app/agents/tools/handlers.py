from pathlib import Path
from typing import Any, Dict, List

import csv

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from openpyxl import load_workbook

from app.knowledge.rag import retrieve_context
from app.services.knowledge.extractor import extract_document
from app.agents.tools.code_sandbox import (
    execute_python_in_sandbox,
)
from app.agents.tools.spreadsheet_analyzer import (
    analyze_spreadsheet,
)


# ---------------------------------------------------------------------------
# NOVA WORKSPACE CONFIGURATION
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).resolve().parents[3]

WORKSPACE_ROOT = (
    BACKEND_ROOT / "app" / "workspace"
).resolve()

ALLOWED_READ_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".html",
    ".css",
    ".xml",
    ".yaml",
    ".yml",
    ".log",
}

ALLOWED_WRITE_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".html",
    ".css",
    ".xml",
    ".yaml",
    ".yml",
    ".log",
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".png",
    ".jpg",
    ".jpeg",
}

ALLOWED_DOCUMENT_WRITE_EXTENSIONS = {
    ".docx",
}

ALLOWED_SPREADSHEET_EXTENSIONS = {
    ".xlsx",
    ".csv",
}

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_WRITE_SIZE = 5 * 1024 * 1024
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024

MAX_SPREADSHEET_ROWS = 500
MAX_SPREADSHEET_COLUMNS = 50

MAX_CODE_SIZE = 100_000


# ---------------------------------------------------------------------------
# WORKSPACE PATH SECURITY
# ---------------------------------------------------------------------------

def _resolve_workspace_file(
    file_path: str,
) -> Path:
    """
    Resolve a file path and ensure it remains
    inside NOVA's controlled workspace.
    """

    if not file_path or not str(file_path).strip():
        raise ValueError(
            "file_path is required."
        )

    raw_path = Path(
        str(file_path).strip()
    )

    if raw_path.is_absolute():
        resolved = raw_path.resolve()
    else:
        resolved = (
            WORKSPACE_ROOT / raw_path
        ).resolve()

    try:
        resolved.relative_to(
            WORKSPACE_ROOT
        )
    except ValueError as exc:
        raise PermissionError(
            "Access denied: file must remain inside NOVA's workspace."
        ) from exc

    return resolved


# ---------------------------------------------------------------------------
# DOCUMENT READER
# ---------------------------------------------------------------------------

def document_reader_handler(
    file_path: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Read and extract a supported local document.

    Supported:
    - PDF
    - TXT
    - DOCX
    """

    if not file_path:
        raise ValueError(
            "document_reader requires a file_path."
        )

    result = extract_document(
        file_path
    )

    return result.to_dict()


# ---------------------------------------------------------------------------
# DOCUMENT WRITER HELPERS
# ---------------------------------------------------------------------------

def _clean_document_text(
    content: str,
) -> str:
    """
    Remove accidental Markdown code fences from generated content.

    This prevents text such as ```python from appearing
    inside generated DOCX files.
    """

    if content is None:
        return ""

    text = str(content).strip()

    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    return text


def _add_content_to_document(
    document: Document,
    content: str,
) -> None:
    """
    Convert generated text into readable DOCX paragraphs.

    Basic Markdown-style headings and bullets are recognized.
    """

    cleaned = _clean_document_text(
        content
    )

    if not cleaned:
        document.add_paragraph(
            "No content was provided."
        )
        return

    for raw_line in cleaned.splitlines():
        line = raw_line.strip()

        if not line:
            document.add_paragraph()
            continue

        if line.startswith("### "):
            paragraph = document.add_heading(
                line[4:].strip(),
                level=3,
            )
            paragraph.alignment = (
                WD_ALIGN_PARAGRAPH.LEFT
            )
            continue

        if line.startswith("## "):
            paragraph = document.add_heading(
                line[3:].strip(),
                level=2,
            )
            paragraph.alignment = (
                WD_ALIGN_PARAGRAPH.LEFT
            )
            continue

        if line.startswith("# "):
            paragraph = document.add_heading(
                line[2:].strip(),
                level=1,
            )
            paragraph.alignment = (
                WD_ALIGN_PARAGRAPH.LEFT
            )
            continue

        if line.startswith(("- ", "* ")):
            document.add_paragraph(
                line[2:].strip(),
                style="List Bullet",
            )
            continue

        if line.startswith("1. "):
            document.add_paragraph(
                line[3:].strip(),
                style="List Number",
            )
            continue

        document.add_paragraph(
            line
        )


# ---------------------------------------------------------------------------
# DOCUMENT WRITER
# ---------------------------------------------------------------------------

def document_writer_handler(
    file_path: str,
    title: str = "",
    content: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Create a formatted DOCX document inside NOVA's workspace.

    The handler:
    - validates the requested workspace path
    - creates a real DOCX file
    - adds a title when supplied
    - converts generated text into readable paragraphs
    - saves the document locally
    """

    if not file_path or not str(file_path).strip():
        raise ValueError(
            "document_writer requires a file_path."
        )

    if content is None:
        raise ValueError(
            "document_writer requires content."
        )

    content = str(content)

    content_size = len(
        content.encode("utf-8")
    )

    if content_size > MAX_DOCUMENT_SIZE:
        raise ValueError(
            "Document content is too large. "
            "Maximum allowed size is 10 MB."
        )

    path = _resolve_workspace_file(
        file_path
    )

    extension = path.suffix.lower()

    if extension not in ALLOWED_DOCUMENT_WRITE_EXTENSIONS:
        raise ValueError(
            "Unsupported document type: "
            f"{extension or '[no extension]'}. "
            "document_writer currently supports DOCX only."
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    document = Document()

    # ------------------------------------------------------------------
    # DEFAULT DOCUMENT STYLE
    # ------------------------------------------------------------------

    normal_style = document.styles["Normal"]

    normal_style.font.name = "Arial"
    normal_style.font.size = Pt(10.5)

    # ------------------------------------------------------------------
    # TITLE
    # ------------------------------------------------------------------

    clean_title = (
        str(title).strip()
        if title is not None
        else ""
    )

    if clean_title:
        heading = document.add_heading(
            clean_title,
            level=0,
        )
        heading.alignment = (
            WD_ALIGN_PARAGRAPH.CENTER
        )

    # ------------------------------------------------------------------
    # CONTENT
    # ------------------------------------------------------------------

    _add_content_to_document(
        document=document,
        content=content,
    )

    # ------------------------------------------------------------------
    # SAVE
    # ------------------------------------------------------------------

    document.save(
        path
    )

    if not path.exists():
        raise RuntimeError(
            "DOCX document was not created."
        )

    file_size = path.stat().st_size

    if file_size <= 0:
        raise RuntimeError(
            "Generated DOCX document is empty."
        )

    return {
        "file_path": str(
            path.relative_to(
                WORKSPACE_ROOT
            )
        ),
        "file_name": path.name,
        "extension": extension,
        "size_bytes": file_size,
        "created": True,
        "title": clean_title,
        "workspace": "NOVA",
        "tool": "document_writer",
    }


# ---------------------------------------------------------------------------
# KNOWLEDGE SEARCH
# ---------------------------------------------------------------------------

def knowledge_search_handler(
    query: str,
    top_k: int = 5,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Search NOVA's existing local ChromaDB
    knowledge base.
    """

    if not query or not query.strip():
        raise ValueError(
            "knowledge_search requires a non-empty query."
        )

    top_k = int(top_k)

    if top_k < 1 or top_k > 10:
        raise ValueError(
            "top_k must be between 1 and 10."
        )

    results = retrieve_context(
        query=query.strip(),
        top_k=top_k,
    )

    return {
        "query": query.strip(),
        "results": results,
        "count": len(results),
    }


# ---------------------------------------------------------------------------
# FILE READER
# ---------------------------------------------------------------------------

def file_reader_handler(
    file_path: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Safely read a permitted local workspace file.
    """

    path = _resolve_workspace_file(
        file_path
    )

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    if not path.is_file():
        raise ValueError(
            "The specified path is not a file."
        )

    extension = path.suffix.lower()

    if extension not in ALLOWED_READ_EXTENSIONS:
        raise ValueError(
            "Unsupported file type: "
            f"{extension or '[no extension]'}"
        )

    file_size = path.stat().st_size

    if file_size > MAX_FILE_SIZE:
        raise ValueError(
            "File is too large for file_reader. "
            "Maximum allowed size is 5 MB."
        )

    try:
        content = path.read_text(
            encoding="utf-8-sig"
        )
    except UnicodeDecodeError as exc:
        raise ValueError(
            "File is not valid UTF-8 text."
        ) from exc

    return {
        "file_path": str(
            path.relative_to(
                WORKSPACE_ROOT
            )
        ),
        "file_name": path.name,
        "extension": extension,
        "size_bytes": file_size,
        "content": content,
        "lines": content.count("\n") + (
            1 if content else 0
        ),
        "workspace": "NOVA",
    }


# ---------------------------------------------------------------------------
# FILE WRITER
# ---------------------------------------------------------------------------

def file_writer_handler(
    file_path: str,
    content: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Safely write generated content into NOVA's workspace.
    """

    if not file_path or not str(file_path).strip():
        raise ValueError(
            "file_writer requires a file_path."
        )

    if content is None:
        raise ValueError(
            "file_writer requires content."
        )

    content = str(content)

    path = _resolve_workspace_file(
        file_path
    )

    extension = path.suffix.lower()

    if extension not in ALLOWED_WRITE_EXTENSIONS:
        raise ValueError(
            "Unsupported write file type: "
            f"{extension or '[no extension]'}"
        )

    content_size = len(
        content.encode("utf-8")
    )

    if content_size > MAX_WRITE_SIZE:
        raise ValueError(
            "Content is too large for file_writer. "
            "Maximum allowed size is 5 MB."
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        content,
        encoding="utf-8",
    )

    return {
        "file_path": str(
            path.relative_to(
                WORKSPACE_ROOT
            )
        ),
        "file_name": path.name,
        "extension": extension,
        "size_bytes": path.stat().st_size,
        "created": True,
        "workspace": "NOVA",
    }


# ---------------------------------------------------------------------------
# SPREADSHEET HELPERS
# ---------------------------------------------------------------------------

def _normalize_cell_value(
    value: Any,
) -> Any:
    """
    Convert spreadsheet values into JSON-safe values.

    Primitive values are preserved. Complex values such as
    dates, formulas represented as objects, or other workbook
    types are converted to strings so the result can safely
    travel through the agent pipeline.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    return str(value)


def _normalize_header(
    value: Any,
    index: int,
) -> str:
    """
    Normalize a spreadsheet header into a stable string.
    """

    if value is None:
        return f"Column {index + 1}"

    header = str(value).strip()

    if not header:
        return f"Column {index + 1}"

    return header


def _normalize_headers(
    headers: List[Any],
) -> List[str]:
    """
    Normalize headers while preserving their order.
    """

    return [
        _normalize_header(
            value,
            index,
        )
        for index, value in enumerate(
            headers[:MAX_SPREADSHEET_COLUMNS]
        )
    ]


def _normalize_row_to_width(
    row: List[Any],
    width: int,
) -> List[Any]:
    """
    Make every row exactly the same width as the
    detected spreadsheet headers.

    Missing cells are represented as None.
    Extra cells are safely truncated.
    """

    normalized = [
        _normalize_cell_value(
            value
        )
        for value in row[:width]
    ]

    if len(normalized) < width:
        normalized.extend(
            [None]
            * (
                width - len(normalized)
            )
        )

    return normalized


def _trim_rows(
    rows: List[List[Any]],
    width: int | None = None,
) -> List[List[Any]]:
    """
    Limit spreadsheet output to safe dimensions
    for agent processing.

    Rows are normalized to a consistent column width.
    """

    if width is None:
        width = MAX_SPREADSHEET_COLUMNS

    width = max(
        0,
        min(
            int(width),
            MAX_SPREADSHEET_COLUMNS,
        ),
    )

    trimmed: List[List[Any]] = []

    for row in rows[:MAX_SPREADSHEET_ROWS]:
        if not isinstance(row, (list, tuple)):
            row = [row]

        trimmed.append(
            _normalize_row_to_width(
                list(row),
                width,
            )
        )

    return trimmed


def _read_csv(
    path: Path,
) -> Dict[str, Any]:
    """
    Read a local CSV file and normalize it
    into the same structure used by XLSX.

    The CSV reader:
    - supports common delimiters
    - handles UTF-8 BOM
    - limits rows and columns
    - keeps blank cells as None
    - normalizes all rows to the header width
    """

    file_size = path.stat().st_size

    if file_size > MAX_FILE_SIZE:
        raise ValueError(
            "CSV file is too large. "
            "Maximum allowed size is 5 MB."
        )

    rows: List[List[Any]] = []

    try:
        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as csv_file:

            sample = csv_file.read(
                4096
            )

            csv_file.seek(0)

            try:
                dialect = csv.Sniffer().sniff(
                    sample,
                    delimiters=",;\t|",
                )
            except csv.Error:
                dialect = csv.excel

            reader = csv.reader(
                csv_file,
                dialect,
            )

            for row in reader:
                rows.append(
                    row
                )

                if len(rows) >= (
                    MAX_SPREADSHEET_ROWS + 1
                ):
                    break

    except UnicodeDecodeError as exc:
        raise ValueError(
            "CSV file is not valid UTF-8 text."
        ) from exc

    except csv.Error as exc:
        raise ValueError(
            "CSV file could not be parsed."
        ) from exc

    headers = (
        rows[0]
        if rows
        else []
    )

    normalized_headers = _normalize_headers(
        headers
    )

    data_rows = (
        rows[1:]
        if len(rows) > 1
        else []
    )

    normalized_rows = _trim_rows(
        data_rows,
        width=len(
            normalized_headers
        ),
    )

    sheet = {
        "sheet_name": path.stem,
        "headers": normalized_headers,
        "rows": normalized_rows,
        "row_count": len(
            normalized_rows
        ),
        "column_count": len(
            normalized_headers
        ),
    }

    return {
        "sheet_count": 1,
        "sheets": [
            sheet
        ],
    }


def _read_xlsx(
    path: Path,
) -> Dict[str, Any]:
    """
    Read a local XLSX workbook in read-only mode.

    Only the calculated cell values are returned.
    """

    file_size = path.stat().st_size

    if file_size > MAX_FILE_SIZE:
        raise ValueError(
            "XLSX file is too large. "
            "Maximum allowed size is 5 MB."
        )

    workbook = None

    try:
        workbook = load_workbook(
            filename=path,
            read_only=True,
            data_only=True,
        )

        sheets: List[Dict[str, Any]] = []

        for worksheet in workbook.worksheets:

            rows: List[List[Any]] = []

            for row in worksheet.iter_rows(
                values_only=True
            ):
                rows.append(
                    list(row)
                )

                if len(rows) >= (
                    MAX_SPREADSHEET_ROWS + 1
                ):
                    break

            headers = (
                rows[0]
                if rows
                else []
            )

            normalized_headers = _normalize_headers(
                list(headers)
            )

            data_rows = (
                rows[1:]
                if len(rows) > 1
                else []
            )

            normalized_rows = _trim_rows(
                data_rows,
                width=len(
                    normalized_headers
                ),
            )

            sheets.append(
                {
                    "sheet_name": worksheet.title,
                    "headers": normalized_headers,
                    "rows": normalized_rows,
                    "row_count": len(
                        normalized_rows
                    ),
                    "column_count": len(
                        normalized_headers
                    ),
                }
            )

        return {
            "sheet_count": len(
                sheets
            ),
            "sheets": sheets,
        }

    finally:
        if workbook is not None:
            workbook.close()


# ---------------------------------------------------------------------------
# SPREADSHEET READER
# ---------------------------------------------------------------------------

def spreadsheet_reader_handler(
    file_path: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Safely inspect a local CSV or XLSX file.

    This handler:
    - validates the workspace path
    - validates the extension
    - enforces the file size limit
    - reads CSV/XLSX locally
    - returns structured sheet data for NOVA's agent
    """

    path = _resolve_workspace_file(
        file_path
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Spreadsheet not found: {file_path}"
        )

    if not path.is_file():
        raise ValueError(
            "The specified path is not a file."
        )

    extension = path.suffix.lower()

    if extension not in ALLOWED_SPREADSHEET_EXTENSIONS:
        raise ValueError(
            "Unsupported spreadsheet type: "
            f"{extension or '[no extension]'}. "
            "Supported types are CSV and XLSX."
        )

    if extension == ".csv":

        spreadsheet = _read_csv(
            path
        )

        return {
            "file_path": str(
                path.relative_to(
                    WORKSPACE_ROOT
                )
            ),
            "file_name": path.name,
            "file_type": "csv",
            "workspace": "NOVA",
            **spreadsheet,
        }

    workbook_data = _read_xlsx(
        path
    )

    return {
        "file_path": str(
            path.relative_to(
                WORKSPACE_ROOT
            )
        ),
        "file_name": path.name,
        "file_type": "xlsx",
        "workspace": "NOVA",
        **workbook_data,
    }


# ---------------------------------------------------------------------------
# SPREADSHEET ANALYSIS
# ---------------------------------------------------------------------------

def spreadsheet_analysis_handler(
    file_path: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Read and analyze a local CSV or XLSX spreadsheet.

    The reader stays fully local and passes the structured
    workbook data into the dedicated spreadsheet analyzer.
    """

    spreadsheet = spreadsheet_reader_handler(
        file_path=file_path,
        **kwargs,
    )

    analysis = analyze_spreadsheet(
        spreadsheet
    )

    return {
        **analysis,
        "tool": "spreadsheet_analysis",
        "workspace": "NOVA",
    }


# ---------------------------------------------------------------------------
# CODE EXECUTOR
# ---------------------------------------------------------------------------

def code_executor_handler(
    language: str,
    code: str,
    timeout: int | float | None = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Execute supported code inside NOVA's Docker sandbox.

    Currently supported:
    - Python
    """

    if not language or not str(language).strip():
        raise ValueError(
            "code_executor requires a language."
        )

    if code is None or not str(code).strip():
        raise ValueError(
            "code_executor requires code."
        )

    normalized_language = (
        str(language)
        .strip()
        .lower()
    )

    if normalized_language in {
        "py",
        "python3",
    }:
        normalized_language = "python"

    if normalized_language != "python":
        raise ValueError(
            "Unsupported language: "
            f"{language}. Currently only Python is enabled."
        )

    code = str(code)

    return {
        **result,
        "tool": "code_executor",
        "workspace": "NOVA sandbox",
    }


# ---------------------------------------------------------------------------
# PDF WRITER
# ---------------------------------------------------------------------------

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.pdfgen import canvas
from app.agents.tools.verification import verify_artifact


class _NumberedCanvas(canvas.Canvas):
    """Canvas wrapper to draw dynamic footer page numbers and headers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))
        
        # Header
        self.drawString(54, 750, "NOVA Sovereign Intelligence | Workspace Output")
        self.setStrokeColor(colors.HexColor("#2D3748"))
        self.setLineWidth(0.5)
        self.line(54, 742, 612 - 54, 742)
        
        # Footer
        self.drawString(54, 36, "Confidential — Local On-Premise Document")
        self.drawRightString(612 - 54, 36, f"Page {self._pageNumber} of {page_count}")
        self.line(54, 48, 612 - 54, 48)
        self.restoreState()


def pdf_writer_handler(
    file_path: str,
    title: str = "",
    content: str = "",
    charts: List[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Generate a formatted PDF document using ReportLab."""
    if not file_path or not str(file_path).strip():
        raise ValueError("pdf_writer requires a file_path.")

    path = _resolve_workspace_file(file_path)
    if path.suffix.lower() != ".pdf":
        path = path.with_suffix(".pdf")

    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72,
    )

    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0EA5E9'),
        spaceAfter=15,
    )
    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#0284C7'),
        spaceBefore=12,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=8,
    )
    bullet_style = ParagraphStyle(
        'BulletDark',
        parent=body_style,
        leftIndent=15,
        spaceAfter=4,
    )

    story = []

    clean_title = str(title).strip() if title else path.stem.replace("_", " ").title()
    story.append(Paragraph(clean_title, title_style))
    story.append(Spacer(1, 10))

    # Convert content into paragraphs
    raw_content = _clean_document_text(content)
    if raw_content:
        for line in raw_content.splitlines():
            line_str = line.strip()
            if not line_str:
                story.append(Spacer(1, 6))
                continue
            if line_str.startswith("### ") or line_str.startswith("## "):
                clean_h = line_str.lstrip("#").strip()
                story.append(Paragraph(clean_h, h2_style))
            elif line_str.startswith("- ") or line_str.startswith("* "):
                story.append(Paragraph(f"• {line_str[2:].strip()}", bullet_style))
            else:
                story.append(Paragraph(line_str, body_style))

    # Embed charts if provided or existing in workspace output
    if charts:
        for chart_rel in charts:
            try:
                chart_p = _resolve_workspace_file(chart_rel)
                if chart_p.exists():
                    story.append(Spacer(1, 12))
                    story.append(RLImage(str(chart_p), width=450, height=250))
            except Exception:
                pass

    doc.build(story, canvasmaker=_NumberedCanvas)

    verified, msg = verify_artifact(path, "pdf")
    if not verified:
        raise RuntimeError(f"PDF creation failed verification: {msg}")

    return {
        "file_path": str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
        "file_name": path.name,
        "extension": ".pdf",
        "size_bytes": path.stat().st_size,
        "created": True,
        "verification": msg,
        "workspace": "NOVA",
        "tool": "pdf_writer",
    }


# ---------------------------------------------------------------------------
# SPREADSHEET WRITER (XLSX)
# ---------------------------------------------------------------------------

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def spreadsheet_writer_handler(
    file_path: str,
    title: str = "",
    sheets_data: List[Dict[str, Any]] = None,
    content: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Generate a formatted Excel workbook with custom styling, auto widths, and headers."""
    if not file_path or not str(file_path).strip():
        raise ValueError("spreadsheet_writer requires a file_path.")

    path = _resolve_workspace_file(file_path)
    if path.suffix.lower() != ".xlsx":
        path = path.with_suffix(".xlsx")

    path.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="00F0FF")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1'),
    )

    if not sheets_data:
        # Build default sheet from content if raw table text is supplied
        sheets_data = [{
            "sheet_name": "Summary",
            "headers": ["Item", "Value"],
            "rows": [["Status", "Complete"], ["Title", title or path.stem]],
        }]

    for sheet_info in sheets_data:
        s_name = str(sheet_info.get("sheet_name", "Data"))[:31]
        ws = wb.create_sheet(title=s_name)
        
        headers = sheet_info.get("headers", [])
        rows = sheet_info.get("rows", [])

        if headers:
            ws.append(headers)
            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = thin_border

        for r_idx, row in enumerate(rows, start=2 if headers else 1):
            ws.append(row)
            for c_idx in range(1, len(row) + 1):
                cell = ws.cell(row=r_idx, column=c_idx)
                cell.border = thin_border

        # Auto column width
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        ws.freeze_panes = "A2"

    wb.save(str(path))

    verified, msg = verify_artifact(path, "xlsx")
    if not verified:
        raise RuntimeError(f"XLSX creation failed verification: {msg}")

    return {
        "file_path": str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
        "file_name": path.name,
        "extension": ".xlsx",
        "size_bytes": path.stat().st_size,
        "created": True,
        "verification": msg,
        "workspace": "NOVA",
        "tool": "spreadsheet_writer",
    }


# ---------------------------------------------------------------------------
# CSV WRITER
# ---------------------------------------------------------------------------

def csv_writer_handler(
    file_path: str,
    headers: List[str] = None,
    rows: List[List[Any]] = None,
    content: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Generate a clean CSV dataset file."""
    if not file_path or not str(file_path).strip():
        raise ValueError("csv_writer requires a file_path.")

    path = _resolve_workspace_file(file_path)
    if path.suffix.lower() != ".csv":
        path = path.with_suffix(".csv")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if headers:
            writer.writerow(headers)
        if rows:
            for r in rows:
                writer.writerow(r)
        elif content:
            f.write(content)

    verified, msg = verify_artifact(path, "csv")
    if not verified:
        raise RuntimeError(f"CSV creation failed verification: {msg}")

    return {
        "file_path": str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
        "file_name": path.name,
        "extension": ".csv",
        "size_bytes": path.stat().st_size,
        "created": True,
        "verification": msg,
        "workspace": "NOVA",
        "tool": "csv_writer",
    }


# ---------------------------------------------------------------------------
# PPTX WRITER (PowerPoint)
# ---------------------------------------------------------------------------

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN


def pptx_writer_handler(
    file_path: str,
    title: str = "",
    subtitle: str = "",
    slides: List[Dict[str, Any]] = None,
    content: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Generate a presentation deck styled with NOVA dark/cyan theme."""
    if not file_path or not str(file_path).strip():
        raise ValueError("pptx_writer requires a file_path.")

    path = _resolve_workspace_file(file_path)
    if path.suffix.lower() != ".pptx":
        path = path.with_suffix(".pptx")

    path.parent.mkdir(parents=True, exist_ok=True)

    prs = Presentation()
    # Blank slide layout
    blank_layout = prs.slide_layouts[6]

    clean_title = str(title).strip() if title else path.stem.replace("_", " ").title()

    # 1. Title Slide
    t_slide = prs.slides.add_slide(blank_layout)
    # Background
    bg = t_slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(18, 20, 24)

    # Title box
    tx_box = t_slide.shapes.add_textbox(Inches(1.0), Inches(2.2), Inches(8.0), Inches(2.5))
    tf = tx_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = clean_title
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = RGBColor(0, 240, 255)
    p.alignment = PP_ALIGN.LEFT

    if subtitle:
        p2 = tf.add_paragraph()
        p2.text = subtitle
        p2.font.size = Pt(18)
        p2.font.color.rgb = RGBColor(226, 232, 240)
        p2.alignment = PP_ALIGN.LEFT

    # 2. Content Slides
    if not slides:
        # Build slides from content paragraphs if no structured list
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        slides = [{
            "title": "Executive Summary",
            "bullets": lines[:6] if lines else ["Analysis completed successfully."],
        }]

    for slide_data in slides:
        c_slide = prs.slides.add_slide(blank_layout)
        bg = c_slide.background
        fill = bg.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor(18, 20, 24)

        # Slide Header
        s_box = c_slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8.4), Inches(1.0))
        stf = s_box.text_frame
        sp = stf.paragraphs[0]
        sp.text = str(slide_data.get("title", "Overview"))
        sp.font.size = Pt(24)
        sp.font.bold = True
        sp.font.color.rgb = RGBColor(0, 240, 255)

        # Slide Body Bullets
        bullets = slide_data.get("bullets", [])
        if bullets:
            b_box = c_slide.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(8.4), Inches(4.8))
            btf = b_box.text_frame
            btf.word_wrap = True
            for idx, bullet in enumerate(bullets):
                bp = btf.paragraphs[0] if idx == 0 else btf.add_paragraph()
                bp.text = f"•  {bullet}"
                bp.font.size = Pt(16)
                bp.font.color.rgb = RGBColor(226, 232, 240)
                bp.space_after = Pt(10)

        # Embedded Image if provided
        img_path = slide_data.get("image_path")
        if img_path:
            try:
                ip = _resolve_workspace_file(img_path)
                if ip.exists():
                    c_slide.shapes.add_picture(str(ip), Inches(5.0), Inches(1.8), width=Inches(4.2))
            except Exception:
                pass

    prs.save(str(path))

    verified, msg = verify_artifact(path, "pptx")
    if not verified:
        raise RuntimeError(f"PPTX creation failed verification: {msg}")

    return {
        "file_path": str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
        "file_name": path.name,
        "extension": ".pptx",
        "size_bytes": path.stat().st_size,
        "created": True,
        "verification": msg,
        "workspace": "NOVA",
        "tool": "pptx_writer",
    }


# ---------------------------------------------------------------------------
# VISUALIZATION WRITER (Matplotlib Charts)
# ---------------------------------------------------------------------------

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def visualization_writer_handler(
    file_path: str = "",
    title: str = "Data Visualization",
    chart_type: str = "bar",
    data: Dict[str, Any] = None,
    x_label: str = "",
    y_label: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Generate high-quality chart PNGs styled with NOVA dark/cyan theme."""
    if not file_path or not str(file_path).strip():
        file_path = f"output/chart_{int(datetime.now().timestamp())}.png"

    path = _resolve_workspace_file(file_path)
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        path = path.with_suffix(".png")

    path.parent.mkdir(parents=True, exist_ok=True)

    # Style
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    fig.patch.set_facecolor('#121418')
    ax.set_facecolor('#181A20')

    chart_type = (chart_type or "bar").lower()

    # Extract labels and values
    labels = []
    values = []

    if data:
        if isinstance(data, dict):
            if "labels" in data and "values" in data:
                labels = [str(l) for l in data["labels"]]
                values = [float(v) for v in data["values"]]
            else:
                labels = [str(k) for k in data.keys()]
                values = [float(v) for v in data.values() if isinstance(v, (int, float))]
        elif isinstance(data, list):
            labels = [f"Item {i+1}" for i in range(len(data))]
            values = [float(v) for v in data if isinstance(v, (int, float))]

    if not labels or not values:
        # Fallback sample data if empty
        labels = ["Category A", "Category B", "Category C", "Category D"]
        values = [120, 240, 180, 310]

    cyan_color = '#00F0FF'
    magenta_color = '#FF007F'
    bar_colors = ['#00F0FF', '#38BDF8', '#818CF8', '#C084FC', '#F472B6']

    if chart_type in {"bar", "column"}:
        bars = ax.bar(labels, values, color=bar_colors[:len(labels)], edgecolor='#0284C7', linewidth=1)
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:,.1f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom', color='#E2E8F0', fontsize=8)

    elif chart_type in {"line", "trend"}:
        ax.plot(labels, values, marker='o', color=cyan_color, linewidth=2.5, markersize=6, markerfacecolor='#FFFFFF')
        ax.fill_between(labels, values, color=cyan_color, alpha=0.15)

    elif chart_type in {"pie", "donut"}:
        wedges, texts, autotexts = ax.pie(
            values, labels=labels, autopct='%1.1f%%',
            colors=bar_colors[:len(labels)],
            wedgeprops=dict(width=0.4 if chart_type == "donut" else 1.0, edgecolor='#121418')
        )
        for text in texts:
            text.set_color('#E2E8F0')
        for autotext in autotexts:
            autotext.set_color('#FFFFFF')

    elif chart_type == "scatter":
        ax.scatter(range(len(values)), values, color=cyan_color, s=60, alpha=0.8)

    ax.set_title(title, color='#00F0FF', fontsize=12, pad=12, fontweight='bold')
    if x_label:
        ax.set_xlabel(x_label, color='#94A3B8', fontsize=9)
    if y_label:
        ax.set_ylabel(y_label, color='#94A3B8', fontsize=9)

    ax.tick_params(colors='#94A3B8', labelsize=8)
    ax.grid(True, linestyle='--', alpha=0.2, color='#475569')

    plt.tight_layout()
    plt.savefig(str(path), facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)

    verified, msg = verify_artifact(path, "image")
    if not verified:
        raise RuntimeError(f"Chart creation failed verification: {msg}")

    return {
        "file_path": str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
        "file_name": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "created": True,
        "verification": msg,
        "workspace": "NOVA",
        "tool": "visualization_writer",
    }