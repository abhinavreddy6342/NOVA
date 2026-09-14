from pathlib import Path
from uuid import uuid4
import csv
import json

from PIL import Image
import pytesseract
from openpyxl import load_workbook

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
    ".csv",
    ".xlsx",
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


SPREADSHEET_EXTENSIONS = {
    ".csv",
    ".xlsx",
}


MAX_UPLOAD_SIZE = 20 * 1024 * 1024

MAX_SPREADSHEET_ROWS = 500
MAX_SPREADSHEET_COLUMNS = 50


# ---------------------------------------------------------------------------
# IMAGE OCR
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# SPREADSHEET HELPERS
# ---------------------------------------------------------------------------

def _normalize_spreadsheet_value(
    value,
) -> str:
    """
    Convert a spreadsheet value into readable text.
    """

    if value is None:
        return ""

    if isinstance(
        value,
        bool,
    ):
        return "True" if value else "False"

    return str(value)


def _normalize_spreadsheet_row(
    row,
) -> list[str]:
    """
    Normalize one spreadsheet row into a bounded list of strings.
    """

    return [
        _normalize_spreadsheet_value(value)
        for value in list(row)[
            :MAX_SPREADSHEET_COLUMNS
        ]
    ]


def _spreadsheet_to_text(
    file_path: Path,
    extension: str,
) -> str:
    """
    Extract a compact, structured text representation from
    a CSV or XLSX file.

    This representation is stored in NOVA's chat attachment
    metadata so the existing chat attachment pipeline can
    understand spreadsheet content locally.
    """

    if extension == ".csv":
        return _csv_to_text(
            file_path
        )

    if extension == ".xlsx":
        return _xlsx_to_text(
            file_path
        )

    raise ValueError(
        f"Unsupported spreadsheet extension: {extension}"
    )


def _csv_to_text(
    file_path: Path,
) -> str:
    """
    Read a CSV file locally and convert it into structured text.
    """

    rows = []

    try:
        with file_path.open(
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
                    _normalize_spreadsheet_row(
                        row
                    )
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

    if not rows:
        return ""

    headers = rows[0]

    data_rows = rows[1:]

    output = [
        "Spreadsheet type: CSV",
        f"Rows analyzed: {len(data_rows)}",
        f"Columns detected: {len(headers)}",
        "",
        "Columns:",
        ", ".join(
            header or f"Column {index + 1}"
            for index, header in enumerate(headers)
        ),
        "",
        "Data:",
    ]

    for row in data_rows:
        values = []

        width = max(
            len(headers),
            len(row),
        )

        for index in range(
            min(
                width,
                MAX_SPREADSHEET_COLUMNS,
            )
        ):
            header = (
                headers[index]
                if index < len(headers)
                else f"Column {index + 1}"
            )

            header = (
                header
                or f"Column {index + 1}"
            )

            value = (
                row[index]
                if index < len(row)
                else ""
            )

            values.append(
                f"{header}={value}"
            )

        output.append(
            " | ".join(values)
        )

    return "\n".join(
        output
    )


def _xlsx_to_text(
    file_path: Path,
) -> str:
    """
    Read an XLSX workbook locally and convert each worksheet
    into a bounded structured text representation.
    """

    workbook = None

    try:
        workbook = load_workbook(
            filename=file_path,
            read_only=True,
            data_only=True,
        )

        output = [
            "Spreadsheet type: XLSX",
            f"Worksheet count: {len(workbook.worksheets)}",
        ]

        for worksheet in workbook.worksheets:

            rows = []

            for row in worksheet.iter_rows(
                values_only=True
            ):
                rows.append(
                    _normalize_spreadsheet_row(
                        row
                    )
                )

                if len(rows) >= (
                    MAX_SPREADSHEET_ROWS + 1
                ):
                    break

            if not rows:
                output.extend(
                    [
                        "",
                        f"Worksheet: {worksheet.title}",
                        "Rows analyzed: 0",
                        "Columns detected: 0",
                    ]
                )
                continue

            headers = rows[0]

            data_rows = rows[1:]

            output.extend(
                [
                    "",
                    f"Worksheet: {worksheet.title}",
                    f"Rows analyzed: {len(data_rows)}",
                    f"Columns detected: {len(headers)}",
                    "",
                    "Columns:",
                    ", ".join(
                        header
                        or f"Column {index + 1}"
                        for index, header in enumerate(
                            headers
                        )
                    ),
                    "",
                    "Data:",
                ]
            )

            for row in data_rows:
                values = []

                width = max(
                    len(headers),
                    len(row),
                )

                for index in range(
                    min(
                        width,
                        MAX_SPREADSHEET_COLUMNS,
                    )
                ):
                    header = (
                        headers[index]
                        if index < len(headers)
                        else f"Column {index + 1}"
                    )

                    header = (
                        header
                        or f"Column {index + 1}"
                    )

                    value = (
                        row[index]
                        if index < len(row)
                        else ""
                    )

                    values.append(
                        f"{header}={value}"
                    )

                output.append(
                    " | ".join(values)
                )

        return "\n".join(
            output
        )

    except Exception as exc:
        raise RuntimeError(
            f"Failed to read XLSX file locally: {exc}"
        ) from exc

    finally:
        if workbook is not None:
            workbook.close()


# ---------------------------------------------------------------------------
# GENERAL CHAT TEXT EXTRACTION
# ---------------------------------------------------------------------------

def _extract_chat_text(
    file_path: Path,
    extension: str,
) -> str:
    """
    Extract text from supported chat attachments.

    PDF/DOCX/TXT:
        Use NOVA's existing extractor.

    CSV/XLSX:
        Use NOVA's local spreadsheet reader.

    Images:
        Use local Tesseract OCR.
    """

    if extension in IMAGE_EXTENSIONS:
        return _extract_image_text(
            file_path
        )

    if extension in SPREADSHEET_EXTENSIONS:
        return _spreadsheet_to_text(
            file_path=file_path,
            extension=extension,
        )

    return extract_text(
        str(file_path)
    )


# ---------------------------------------------------------------------------
# SAVE CHAT FILE
# ---------------------------------------------------------------------------

def save_chat_file(
    filename: str,
    file_bytes: bytes,
    content_type: str = "",
) -> dict:
    """
    Save a chat attachment into NOVA's local workspace.

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
    """

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
            "Use PDF, TXT, DOCX, CSV, XLSX, PNG, JPG, JPEG, or WEBP."
        )

    if not file_bytes:
        raise ValueError(
            "The uploaded file is empty."
        )

    if len(file_bytes) > MAX_UPLOAD_SIZE:
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

        if extension in SPREADSHEET_EXTENSIONS:
            raise ValueError(
                "No readable spreadsheet data was found in the file."
            )

        raise ValueError(
            "No readable text was found in the file."
        )

    if extension in IMAGE_EXTENSIONS:
        file_type = "image"
    elif extension in SPREADSHEET_EXTENSIONS:
        file_type = "spreadsheet"
    else:
        file_type = "document"

    metadata = {
        "file_id": file_id,
        "filename": original_name,
        "stored_name": stored_name,
        "content_type": content_type,
        "extension": extension,
        "file_type": file_type,
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
        "file_type": file_type,
        "characters": len(
            extracted_text
        ),
    }


# ---------------------------------------------------------------------------
# LOAD CHAT FILE
# ---------------------------------------------------------------------------

def load_chat_file(
    file_id: str,
) -> dict:
    """
    Load locally stored chat attachment metadata.
    """

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