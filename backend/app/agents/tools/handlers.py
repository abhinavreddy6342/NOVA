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
    """

    if value is None:
        return None

    if isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    return str(value)


def _trim_rows(
    rows: List[List[Any]],
) -> List[List[Any]]:
    """
    Limit spreadsheet output to safe
    dimensions for agent processing.
    """

    trimmed = []

    for row in rows[:MAX_SPREADSHEET_ROWS]:
        trimmed.append(
            [
                _normalize_cell_value(
                    value
                )
                for value in row[
                    :MAX_SPREADSHEET_COLUMNS
                ]
            ]
        )

    return trimmed


def _read_csv(
    path: Path,
) -> Dict[str, Any]:
    """
    Read a local CSV file and normalize it
    into the same structure used by XLSX.
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

            reader = csv.reader(
                csv_file
            )

            for row in reader:
                rows.append(row)

                if len(rows) >= MAX_SPREADSHEET_ROWS:
                    break

    except UnicodeDecodeError as exc:
        raise ValueError(
            "CSV file is not valid UTF-8 text."
        ) from exc

    headers = (
        rows[0]
        if rows
        else []
    )

    data_rows = (
        rows[1:]
        if len(rows) > 1
        else []
    )

    normalized_headers = [
        _normalize_cell_value(
            value
        )
        for value in headers[
            :MAX_SPREADSHEET_COLUMNS
        ]
    ]

    normalized_rows = _trim_rows(
        data_rows
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

        sheets = []

        for worksheet in workbook.worksheets:

            rows: List[List[Any]] = []

            for row in worksheet.iter_rows(
                values_only=True
            ):
                rows.append(
                    list(row)
                )

                if len(rows) >= MAX_SPREADSHEET_ROWS:
                    break

            headers = (
                rows[0]
                if rows
                else []
            )

            data_rows = (
                rows[1:]
                if len(rows) > 1
                else []
            )

            sheets.append(
                {
                    "sheet_name": worksheet.title,
                    "headers": [
                        _normalize_cell_value(
                            value
                        )
                        for value in headers[
                            :MAX_SPREADSHEET_COLUMNS
                        ]
                    ],
                    "rows": _trim_rows(
                        data_rows
                    ),
                    "row_count": len(
                        data_rows
                    ),
                    "column_count": min(
                        len(headers),
                        MAX_SPREADSHEET_COLUMNS,
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
            f"{extension or '[no extension]'}"
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

    code_size = len(
        code.encode("utf-8")
    )

    if code_size > MAX_CODE_SIZE:
        raise ValueError(
            "Code exceeds the maximum allowed size."
        )

    result = execute_python_in_sandbox(
        code=code,
        timeout=timeout,
    )

    return {
        **result,
        "tool": "code_executor",
        "workspace": "NOVA sandbox",
    }