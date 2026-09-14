from __future__ import annotations

from collections import Counter
from datetime import datetime
from statistics import mean, median, stdev
from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np


MAX_ANALYSIS_ROWS = 5000
MAX_ANALYSIS_COLUMNS = 100
MAX_TOP_VALUES = 5


def _to_number(value: Any) -> float | None:
    """Convert a spreadsheet value to a number when possible."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
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


def _column_name(header: Any, index: int) -> str:
    if header is None:
        return f"Column {index + 1}"
    name = str(header).strip()
    return name if name else f"Column {index + 1}"


def _cell_is_blank(value: Any) -> bool:
    if value is None:
        return True
    if pd.isna(value):
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _detect_domain(headers: List[str]) -> str:
    """Deterministically infer likely domain based on column header keywords."""
    clean_headers = [h.lower() for h in headers]
    joined = " ".join(clean_headers)

    if any(k in joined for k in ["request", "employee", "dept", "department", "salary", "wage"]):
        return "HR / Internal Requests"
    if any(k in joined for k in ["sales", "revenue", "product", "customer", "order", "price", "quantity"]):
        return "Sales & Commercial"
    if any(k in joined for k in ["maint", "maintenance", "failure", "repair", "downtime", "equipment", "asset"]):
        return "Industrial Maintenance & Reliability"
    if any(k in joined for k in ["invoice", "payment", "amount", "budget", "cost", "expense", "transaction"]):
        return "Financial & Accounting"
    if any(k in joined for k in ["log", "latency", "error", "status", "response_time"]):
        return "System Operations & Performance"
    return "Structured Tabular Dataset"


def analyze_sheet(sheet: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze one structured spreadsheet sheet using pandas/numpy with rich stats."""
    headers = sheet.get("headers", [])
    rows = sheet.get("rows", [])

    if not isinstance(headers, list):
        headers = []
    if not isinstance(rows, list):
        rows = []

    norm_headers = [_column_name(h, i) for i, h in enumerate(headers[:MAX_ANALYSIS_COLUMNS])]

    if not rows:
        return {
            "sheet_name": sheet.get("sheet_name", "Unknown"),
            "row_count": 0,
            "column_count": len(norm_headers),
            "headers": norm_headers,
            "numeric_columns": [],
            "numeric_summary": {},
            "highest_numeric_value": None,
            "lowest_numeric_value": None,
            "column_profiles": {},
            "insights": {
                "row_count": 0,
                "column_count": len(norm_headers),
                "numeric_column_count": 0,
                "text_column_count": 0,
                "numeric_columns": [],
                "text_columns": [],
                "columns_with_missing_values": [],
                "total_missing_values": 0,
            },
            "workspace": "NOVA",
        }

    # Convert to DataFrame
    df = pd.DataFrame(rows[:MAX_ANALYSIS_ROWS], columns=norm_headers)

    column_profiles: Dict[str, Dict[str, Any]] = {}
    numeric_columns: List[str] = []
    text_columns: List[str] = []
    numeric_summary: Dict[str, Any] = {}
    date_columns: List[str] = []

    duplicate_rows_count = int(df.duplicated().sum())

    for col in norm_headers:
        series = df[col]
        total_count = len(series)
        non_empty = [v for v in series if not _cell_is_blank(v)]
        non_empty_count = len(non_empty)
        missing_count = total_count - non_empty_count

        numeric_vals = [n for v in non_empty if (n := _to_number(v)) is not None]

        profile: Dict[str, Any] = {
            "non_empty_count": non_empty_count,
            "missing_count": missing_count,
            "missing_percentage": round((missing_count / total_count * 100), 2) if total_count > 0 else 0,
            "unique_count": len(set(str(v).strip() for v in non_empty)),
        }

        # Check if numeric
        if len(numeric_vals) > 0 and len(numeric_vals) >= (non_empty_count * 0.5):
            profile["data_type"] = "numeric"
            numeric_columns.append(col)

            num_series = pd.Series(numeric_vals)
            s_sum = float(num_series.sum())
            s_mean = float(num_series.mean())
            s_median = float(num_series.median())
            s_min = float(num_series.min())
            s_max = float(num_series.max())
            s_range = s_max - s_min
            s_std = float(num_series.std()) if len(num_series) > 1 else 0.0

            q25 = float(num_series.quantile(0.25))
            q75 = float(num_series.quantile(0.75))

            sorted_num = sorted(numeric_vals, reverse=True)

            num_stats = {
                "count": len(numeric_vals),
                "sum": s_sum,
                "average": s_mean,
                "median": s_median,
                "minimum": s_min,
                "maximum": s_max,
                "range": s_range,
                "std_dev": s_std,
                "quantile_25": q25,
                "quantile_75": q75,
                "top_values": sorted_num[:MAX_TOP_VALUES],
                "bottom_values": sorted(numeric_vals)[:MAX_TOP_VALUES],
            }
            profile["numeric"] = num_stats
            numeric_summary[col] = num_stats
        else:
            # Check if date/time
            date_parsed = pd.to_datetime(pd.Series(non_empty), errors="coerce")
            valid_dates = date_parsed.dropna()

            if len(valid_dates) > 0 and len(valid_dates) >= (non_empty_count * 0.5):
                profile["data_type"] = "date"
                date_columns.append(col)
                profile["date_summary"] = {
                    "earliest": valid_dates.min().strftime("%Y-%m-%d"),
                    "latest": valid_dates.max().strftime("%Y-%m-%d"),
                    "timespan_days": int((valid_dates.max() - valid_dates.min()).days),
                }
            elif non_empty_count > 0:
                profile["data_type"] = "text"
                text_columns.append(col)
            else:
                profile["data_type"] = "empty"

            # Categorical value counts
            cat_counter = Counter(str(v).strip() for v in non_empty)
            if cat_counter:
                profile["top_values"] = [
                    {"value": val, "count": cnt}
                    for val, cnt in cat_counter.most_common(MAX_TOP_VALUES)
                ]

        column_profiles[col] = profile

    # Correlations between numeric columns
    correlations: Dict[str, Dict[str, float]] = {}
    if len(numeric_columns) >= 2:
        try:
            num_df = pd.DataFrame()
            for col in numeric_columns:
                num_df[col] = df[col].apply(_to_number)
            corr_matrix = num_df.corr().fillna(0)
            for c1 in numeric_columns:
                correlations[c1] = {}
                for c2 in numeric_columns:
                    if c1 != c2:
                        correlations[c1][c2] = round(float(corr_matrix.loc[c1, c2]), 4)
        except Exception:
            pass

    # Grouped aggregations (if categorical + numeric exist)
    grouped_summaries: Dict[str, Any] = {}
    if text_columns and numeric_columns:
        first_text = text_columns[0]
        first_num = numeric_columns[0]
        try:
            grp_df = df.copy()
            grp_df[first_num] = grp_df[first_num].apply(_to_number)
            grp_summary = (
                grp_df.groupby(first_text)[first_num]
                .agg(["count", "sum", "mean"])
                .reset_index()
                .sort_values(by="sum", ascending=False)
                .head(5)
            )
            grouped_summaries[f"{first_num}_by_{first_text}"] = [
                {
                    first_text: str(r[first_text]),
                    "count": int(r["count"]),
                    "sum": float(r["sum"]),
                    "mean": float(r["mean"]),
                }
                for _, r in grp_summary.iterrows()
            ]
        except Exception:
            pass

    # Global Highest / Lowest Numeric
    highest_value = None
    lowest_value = None

    for name, stats in numeric_summary.items():
        if stats.get("maximum") is not None:
            if highest_value is None or stats["maximum"] > highest_value["value"]:
                highest_value = {"column": name, "value": stats["maximum"]}
        if stats.get("minimum") is not None:
            if lowest_value is None or stats["minimum"] < lowest_value["value"]:
                lowest_value = {"column": name, "value": stats["minimum"]}

    cols_with_missing = [c for c, p in column_profiles.items() if p.get("missing_count", 0) > 0]
    total_missing = sum(p.get("missing_count", 0) for p in column_profiles.values())

    domain = _detect_domain(norm_headers)

    insights = {
        "row_count": len(rows),
        "column_count": len(norm_headers),
        "numeric_column_count": len(numeric_columns),
        "text_column_count": len(text_columns),
        "date_column_count": len(date_columns),
        "numeric_columns": numeric_columns,
        "text_columns": text_columns,
        "date_columns": date_columns,
        "columns_with_missing_values": cols_with_missing,
        "total_missing_values": total_missing,
        "duplicate_rows": duplicate_rows_count,
        "domain_characterization": domain,
        "correlations": correlations,
        "grouped_summaries": grouped_summaries,
    }

    return {
        "sheet_name": sheet.get("sheet_name", "Unknown"),
        "row_count": len(rows),
        "column_count": len(norm_headers),
        "headers": norm_headers,
        "numeric_columns": numeric_columns,
        "numeric_summary": numeric_summary,
        "highest_numeric_value": highest_value,
        "lowest_numeric_value": lowest_value,
        "column_profiles": column_profiles,
        "insights": insights,
        "workspace": "NOVA",
    }


def analyze_spreadsheet(spreadsheet: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze structured spreadsheet data across all sheets."""
    sheets = spreadsheet.get("sheets", [])
    if not isinstance(sheets, list):
        sheets = []

    analyzed_sheets = []
    for sheet in sheets:
        if isinstance(sheet, dict):
            analyzed_sheets.append(analyze_sheet(sheet))

    numeric_columns_detected = sorted(
        {col for sheet in analyzed_sheets for col in sheet.get("numeric_columns", [])}
    )

    text_columns_detected = sorted(
        {
            col
            for sheet in analyzed_sheets
            for col in sheet.get("insights", {}).get("text_columns", [])
        }
    )

    total_rows = sum(sheet.get("row_count", 0) for sheet in analyzed_sheets)
    total_missing = sum(
        sheet.get("insights", {}).get("total_missing_values", 0) for sheet in analyzed_sheets
    )

    highest_value = None
    lowest_value = None

    for sheet in analyzed_sheets:
        sh_high = sheet.get("highest_numeric_value")
        if sh_high:
            if highest_value is None or sh_high["value"] > highest_value["value"]:
                highest_value = {
                    "sheet_name": sheet.get("sheet_name"),
                    "column": sh_high["column"],
                    "value": sh_high["value"],
                }
        sh_low = sheet.get("lowest_numeric_value")
        if sh_low:
            if lowest_value is None or sh_low["value"] < lowest_value["value"]:
                lowest_value = {
                    "sheet_name": sheet.get("sheet_name"),
                    "column": sh_low["column"],
                    "value": sh_low["value"],
                }

    domain = (
        analyzed_sheets[0].get("insights", {}).get("domain_characterization", "Structured Dataset")
        if analyzed_sheets
        else "Structured Dataset"
    )

    return {
        "file_name": spreadsheet.get("file_name"),
        "file_path": spreadsheet.get("file_path"),
        "file_type": spreadsheet.get("file_type"),
        "sheet_count": len(analyzed_sheets),
        "sheets": analyzed_sheets,
        "analysis": {
            "numeric_columns_detected": numeric_columns_detected,
            "text_columns_detected": text_columns_detected,
            "total_rows_analyzed": total_rows,
            "total_missing_values": total_missing,
            "highest_numeric_value": highest_value,
            "lowest_numeric_value": lowest_value,
            "domain_characterization": domain,
        },
        "workspace": "NOVA",
    }