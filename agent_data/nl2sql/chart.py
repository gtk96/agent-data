"""Chart suggestion logic for NL2SQL query results.

Analyzes query result data and suggests a suitable chart type.
No external dependencies — pure Python analysis.
"""
import re
from typing import Any, Dict, List, Optional


def _is_numeric(val: Any) -> bool:
    """Check if a value can be treated as numeric."""
    if isinstance(val, (int, float)):
        return True
    if isinstance(val, str):
        try:
            float(val.replace(",", "").replace("¥", "").replace("$", "").strip())
            return True
        except ValueError:
            return False
    return False


def _to_numeric(val: Any) -> float:
    """Convert a value to float."""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", "").replace("¥", "").replace("$", "").strip()
    return float(s)


def _is_date_like(val: Any) -> bool:
    """Check if a value looks like a date or time period."""
    if not isinstance(val, str):
        return False
    date_patterns = [
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",  # 2024-01-15
        r"\d{1,2}月",                        # 3月
        r"\d{4}年",                          # 2024年
        r"(周|月|季|年)度",                    # 周度/月度/季度/年度
        r"(周[一二三四五六日天])",              # 周一~周日
    ]
    return any(re.search(p, val) for p in date_patterns)


def suggest_chart(
    rows: List[Dict[str, Any]],
    columns: List[str],
    max_rows: int = 30,
) -> Optional[Dict[str, Any]]:
    """Analyze query result data and suggest a chart configuration.

    Returns None if data is not suitable for visualization.
    Returns a dict with chart type, labels, datasets if suitable.

    Args:
        rows: Query result rows.
        columns: Column names.
        max_rows: Max rows to chart (too many = no chart).

    Returns:
        Chart config dict or None.
    """
    if not rows or len(rows) > max_rows:
        return None

    if len(columns) < 2:
        return None

    # Identify label column (first non-numeric, or first column)
    label_col = None
    numeric_cols = []

    for col in columns:
        vals = [row.get(col) for row in rows]
        # Check if all values in this column are numeric
        all_numeric = all(_is_numeric(v) for v in vals)
        if all_numeric and not numeric_cols:
            # First numeric column might be labels if it looks like dates
            pass
        if all_numeric:
            numeric_cols.append(col)
        elif label_col is None:
            label_col = col

    # No numeric columns = no chart
    if not numeric_cols:
        return None

    # Single numeric value = no chart
    if len(rows) == 1 and len(numeric_cols) == 1:
        return None

    # If no label column found, use first column as labels
    if label_col is None:
        label_col = columns[0]

    # Extract labels
    labels = [str(row.get(label_col, "")) for row in rows]

    # Check if labels look like dates → line chart
    is_date_axis = sum(_is_date_like(v) for v in labels) >= len(labels) * 0.5

    # Build datasets
    datasets = []
    for col in numeric_cols:
        data = [_to_numeric(row.get(col, 0)) for row in rows]
        datasets.append({
            "label": col,
            "data": data,
        })

    # Choose chart type
    if is_date_axis:
        chart_type = "line"
    elif len(numeric_cols) == 1 and len(rows) <= 5 and all(d > 0 for d in datasets[0]["data"]):
        chart_type = "pie"
    else:
        chart_type = "bar"

    return {
        "type": chart_type,
        "labels": labels,
        "datasets": datasets,
    }
