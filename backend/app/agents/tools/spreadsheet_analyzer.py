from __future__ import annotations

from statistics import mean, median
from typing import Any, Dict, List


MAX_ANALYSIS_ROWS = 500
MAX_ANALYSIS_COLUMNS = 50


def _to_number(
    value: Any,
) -> float | None:
    """
    Convert a spreadsheet value to a number when possible.

    Handles:
    - int
    - float
    - numeric strings from CSV
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(
        value,
        (int, float),
    ):
        return float(value)

    if isinstance(value, str):
        cleaned = value.strip()

        if not cleaned:
            return None

        cleaned = cleaned.replace(
            ",",
            "",
        )

        try:
            return float(cleaned)
        except ValueError:
            return None

    return None


def _is_number(
    value: Any,
) -> bool:
    """
    Check whether a spreadsheet value is numeric.
    """

    return _to_number(value) is not None


def _numeric_columns(
    headers: List[Any],
    rows: List[List[Any]],
) -> Dict[str, List[float]]:
    """
    Detect numeric spreadsheet columns.
    """

    columns: Dict[str, List[float]] = {}

    for index, header in enumerate(
        headers[:MAX_ANALYSIS_COLUMNS]
    ):
        name = (
            str(header).strip()
            if header is not None
            else f"Column {index + 1}"
        )

        values: List[float] = []

        for row in rows[:MAX_ANALYSIS_ROWS]:
            if index >= len(row):
                continue

            number = _to_number(
                row[index]
            )

            if number is not None:
                values.append(
                    number
                )

        if values:
            columns[name] = values

    return columns


def analyze_sheet(
    sheet: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Analyze one structured spreadsheet sheet.
    """

    headers = sheet.get(
        "headers",
        [],
    )

    rows = sheet.get(
        "rows",
        [],
    )

    if not isinstance(headers, list):
        headers = []

    if not isinstance(rows, list):
        rows = []

    numeric_columns = _numeric_columns(
        headers=headers,
        rows=rows,
    )

    numeric_summary: Dict[str, Any] = {}

    for name, values in numeric_columns.items():
        if not values:
            continue

        numeric_summary[name] = {
            "count": len(values),
            "sum": sum(values),
            "average": mean(values),
            "median": median(values),
            "minimum": min(values),
            "maximum": max(values),
        }

    highest_value = None

    for name, values in numeric_columns.items():
        if not values:
            continue

        candidate = {
            "column": name,
            "value": max(values),
        }

        if (
            highest_value is None
            or candidate["value"]
            > highest_value["value"]
        ):
            highest_value = candidate

    lowest_value = None

    for name, values in numeric_columns.items():
        if not values:
            continue

        candidate = {
            "column": name,
            "value": min(values),
        }

        if (
            lowest_value is None
            or candidate["value"]
            < lowest_value["value"]
        ):
            lowest_value = candidate

    return {
        "sheet_name": sheet.get(
            "sheet_name",
            "Unknown",
        ),
        "row_count": len(rows),
        "column_count": len(headers),
        "headers": headers,
        "numeric_columns": list(
            numeric_columns.keys()
        ),
        "numeric_summary": numeric_summary,
        "highest_numeric_value": highest_value,
        "lowest_numeric_value": lowest_value,
    }


def analyze_spreadsheet(
    spreadsheet: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Analyze the structured output produced by
    spreadsheet_reader_handler.
    """

    sheets = spreadsheet.get(
        "sheets",
        [],
    )

    if not isinstance(sheets, list):
        sheets = []

    analyzed_sheets = []

    for sheet in sheets:
        if not isinstance(sheet, dict):
            continue

        analyzed_sheets.append(
            analyze_sheet(sheet)
        )

    return {
        "file_name": spreadsheet.get(
            "file_name"
        ),
        "file_path": spreadsheet.get(
            "file_path"
        ),
        "file_type": spreadsheet.get(
            "file_type"
        ),
        "sheet_count": len(
            analyzed_sheets
        ),
        "sheets": analyzed_sheets,
        "analysis": {
            "numeric_columns_detected": sorted(
                {
                    column
                    for sheet in analyzed_sheets
                    for column in sheet.get(
                        "numeric_columns",
                        [],
                    )
                }
            ),
        },
        "workspace": "NOVA",
    }