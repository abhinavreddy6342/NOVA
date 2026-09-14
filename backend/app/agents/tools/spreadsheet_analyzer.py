from __future__ import annotations

from collections import Counter
from statistics import mean, median
from typing import Any, Dict, List


MAX_ANALYSIS_ROWS = 500
MAX_ANALYSIS_COLUMNS = 50
MAX_TOP_VALUES = 5


def _to_number(
    value: Any,
) -> float | None:
    """
    Convert a spreadsheet value to a number when possible.

    Handles:
    - int
    - float
    - numeric strings from CSV
    - comma-separated numeric strings

    Boolean values are excluded because True/False should not
    be treated as spreadsheet numeric measurements.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        cleaned = value.strip()

        if not cleaned:
            return None

        cleaned = cleaned.replace(",", "")

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


def _column_name(
    header: Any,
    index: int,
) -> str:
    """
    Produce a stable column name.
    """

    if header is None:
        return f"Column {index + 1}"

    name = str(header).strip()

    return name if name else f"Column {index + 1}"


def _cell_is_blank(
    value: Any,
) -> bool:
    """
    Determine whether a spreadsheet cell should be treated
    as missing/blank.
    """

    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    return False


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
        name = _column_name(
            header,
            index,
        )

        values: List[float] = []

        for row in rows[:MAX_ANALYSIS_ROWS]:
            if index >= len(row):
                continue

            number = _to_number(
                row[index]
            )

            if number is not None:
                values.append(number)

        if values:
            columns[name] = values

    return columns


def _column_profile(
    headers: List[Any],
    rows: List[List[Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Build a general profile for every spreadsheet column.

    The profile captures:
    - data type
    - non-empty count
    - missing count
    - unique count
    - numeric statistics
    - common categorical values
    """

    profiles: Dict[str, Dict[str, Any]] = {}

    limited_headers = headers[:MAX_ANALYSIS_COLUMNS]
    limited_rows = rows[:MAX_ANALYSIS_ROWS]

    for index, header in enumerate(limited_headers):
        name = _column_name(
            header,
            index,
        )

        values: List[Any] = []

        for row in limited_rows:
            if index >= len(row):
                values.append(None)
                continue

            values.append(
                row[index]
            )

        non_empty_values = [
            value
            for value in values
            if not _cell_is_blank(value)
        ]

        missing_count = (
            len(values) - len(non_empty_values)
        )

        numeric_values = [
            number
            for value in non_empty_values
            if (number := _to_number(value))
            is not None
        ]

        unique_values = {
            str(value).strip()
            for value in non_empty_values
        }

        categorical_counter = Counter(
            str(value).strip()
            for value in non_empty_values
            if _to_number(value) is None
        )

        is_numeric_column = bool(
            numeric_values
        )

        if is_numeric_column:
            data_type = "numeric"
        elif non_empty_values:
            data_type = "text"
        else:
            data_type = "empty"

        profile: Dict[str, Any] = {
            "data_type": data_type,
            "non_empty_count": len(
                non_empty_values
            ),
            "missing_count": missing_count,
            "unique_count": len(
                unique_values
            ),
        }

        if numeric_values:
            profile["numeric"] = {
                "count": len(
                    numeric_values
                ),
                "sum": sum(
                    numeric_values
                ),
                "average": mean(
                    numeric_values
                ),
                "median": median(
                    numeric_values
                ),
                "minimum": min(
                    numeric_values
                ),
                "maximum": max(
                    numeric_values
                ),
                "range": max(
                    numeric_values
                )
                - min(
                    numeric_values
                ),
            }

            sorted_numeric = sorted(
                numeric_values,
                reverse=True,
            )

            profile["numeric"][
                "top_values"
            ] = sorted_numeric[
                :MAX_TOP_VALUES
            ]

            profile["numeric"][
                "bottom_values"
            ] = sorted(
                numeric_values
            )[
                :MAX_TOP_VALUES
            ]

        if categorical_counter:
            profile[
                "top_values"
            ] = [
                {
                    "value": value,
                    "count": count,
                }
                for value, count in (
                    categorical_counter.most_common(
                        MAX_TOP_VALUES
                    )
                )
            ]

        profiles[name] = profile

    return profiles


def _find_highest_numeric_value(
    numeric_columns: Dict[str, List[float]],
) -> Dict[str, Any] | None:
    """
    Find the highest numeric value across all numeric columns.
    """

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

    return highest_value


def _find_lowest_numeric_value(
    numeric_columns: Dict[str, List[float]],
) -> Dict[str, Any] | None:
    """
    Find the lowest numeric value across all numeric columns.
    """

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

    return lowest_value


def _build_insights(
    headers: List[Any],
    rows: List[List[Any]],
    profiles: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build high-level spreadsheet insights.
    """

    numeric_columns = [
        name
        for name, profile in profiles.items()
        if profile.get("data_type") == "numeric"
    ]

    text_columns = [
        name
        for name, profile in profiles.items()
        if profile.get("data_type") == "text"
    ]

    columns_with_missing_values = [
        name
        for name, profile in profiles.items()
        if profile.get(
            "missing_count",
            0,
        )
        > 0
    ]

    total_missing_values = sum(
        profile.get(
            "missing_count",
            0,
        )
        for profile in profiles.values()
    )

    return {
        "row_count": len(rows),
        "column_count": len(headers),
        "numeric_column_count": len(
            numeric_columns
        ),
        "text_column_count": len(
            text_columns
        ),
        "numeric_columns": numeric_columns,
        "text_columns": text_columns,
        "columns_with_missing_values": (
            columns_with_missing_values
        ),
        "total_missing_values": (
            total_missing_values
        ),
    }


def analyze_sheet(
    sheet: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Analyze one structured spreadsheet sheet.

    The function remains compatible with the original
    spreadsheet analyzer output while adding richer
    column profiling and spreadsheet-level insights.
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

        sorted_values = sorted(
            values,
            reverse=True,
        )

        numeric_summary[name] = {
            "count": len(values),
            "sum": sum(values),
            "average": mean(values),
            "median": median(values),
            "minimum": min(values),
            "maximum": max(values),
            "range": max(values) - min(values),
            "top_values": sorted_values[
                :MAX_TOP_VALUES
            ],
            "bottom_values": sorted(
                values
            )[:MAX_TOP_VALUES],
        }

    profiles = _column_profile(
        headers=headers,
        rows=rows,
    )

    highest_value = _find_highest_numeric_value(
        numeric_columns
    )

    lowest_value = _find_lowest_numeric_value(
        numeric_columns
    )

    insights = _build_insights(
        headers=headers,
        rows=rows,
        profiles=profiles,
    )

    return {
        "sheet_name": sheet.get(
            "sheet_name",
            "Unknown",
        ),
        "row_count": len(rows),
        "column_count": len(headers),
        "headers": headers,

        # Backward-compatible fields
        "numeric_columns": list(
            numeric_columns.keys()
        ),
        "numeric_summary": numeric_summary,
        "highest_numeric_value": highest_value,
        "lowest_numeric_value": lowest_value,

        # Extended analysis
        "column_profiles": profiles,
        "insights": insights,

        "workspace": "NOVA",
    }


def analyze_spreadsheet(
    spreadsheet: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Analyze the structured output produced by
    spreadsheet_reader_handler.

    Supports multiple sheets and produces:
    - per-sheet analysis
    - numeric summaries
    - column profiles
    - missing-value information
    - categorical summaries
    - spreadsheet-level insights
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

    numeric_columns_detected = sorted(
        {
            column
            for sheet in analyzed_sheets
            for column in sheet.get(
                "numeric_columns",
                [],
            )
        }
    )

    text_columns_detected = sorted(
        {
            column
            for sheet in analyzed_sheets
            for column in sheet.get(
                "insights",
                {},
            ).get(
                "text_columns",
                [],
            )
        }
    )

    total_rows = sum(
        sheet.get(
            "row_count",
            0,
        )
        for sheet in analyzed_sheets
    )

    total_missing_values = sum(
        sheet.get(
            "insights",
            {},
        ).get(
            "total_missing_values",
            0,
        )
        for sheet in analyzed_sheets
    )

    highest_value = None
    lowest_value = None

    for sheet in analyzed_sheets:
        sheet_highest = sheet.get(
            "highest_numeric_value"
        )

        if sheet_highest is not None:
            if (
                highest_value is None
                or sheet_highest["value"]
                > highest_value["value"]
            ):
                highest_value = {
                    "sheet_name": sheet.get(
                        "sheet_name"
                    ),
                    "column": sheet_highest[
                        "column"
                    ],
                    "value": sheet_highest[
                        "value"
                    ],
                }

        sheet_lowest = sheet.get(
            "lowest_numeric_value"
        )

        if sheet_lowest is not None:
            if (
                lowest_value is None
                or sheet_lowest["value"]
                < lowest_value["value"]
            ):
                lowest_value = {
                    "sheet_name": sheet.get(
                        "sheet_name"
                    ),
                    "column": sheet_lowest[
                        "column"
                    ],
                    "value": sheet_lowest[
                        "value"
                    ],
                }

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
            "numeric_columns_detected": (
                numeric_columns_detected
            ),
            "text_columns_detected": (
                text_columns_detected
            ),
            "total_rows_analyzed": total_rows,
            "total_missing_values": (
                total_missing_values
            ),
            "highest_numeric_value": (
                highest_value
            ),
            "lowest_numeric_value": (
                lowest_value
            ),
        },

        "workspace": "NOVA",
    }