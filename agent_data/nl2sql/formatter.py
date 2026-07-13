"""Result formatter for NL2SQL."""

from typing import Any, Dict, List


class ResultFormatter:
    """Query result formatter.

    Formats query results for display and LLM consumption.
    """

    @staticmethod
    def to_table_text(data: List[Dict[str, Any]], max_rows: int = 20) -> str:
        """Convert query results to text table.

        Args:
            data: List of result rows.
            max_rows: Maximum rows to display.

        Returns:
            Formatted table string.
        """
        if not data:
            return "No results found."

        # Get column names from first row
        columns = list(data[0].keys())

        # Limit rows
        display_data = data[:max_rows]

        # Calculate column widths
        col_widths = {col: len(col) for col in columns}
        for row in display_data:
            for col in columns:
                val_str = str(row.get(col, ""))
                col_widths[col] = max(col_widths[col], min(len(val_str), 30))

        # Build table
        lines = []

        # Header
        header = " | ".join(col.ljust(col_widths[col]) for col in columns)
        lines.append(header)

        # Separator
        separator = "-+-".join("-" * col_widths[col] for col in columns)
        lines.append(separator)

        # Data rows
        for row in display_data:
            row_str = " | ".join(
                str(row.get(col, "")).ljust(col_widths[col])[:30] for col in columns
            )
            lines.append(row_str)

        # Truncation notice
        if len(data) > max_rows:
            lines.append(f"\n... ({len(data) - max_rows} more rows)")

        return "\n".join(lines)

    @staticmethod
    def to_summary(data: List[Dict[str, Any]]) -> str:
        """Generate data summary.

        Args:
            data: List of result rows.

        Returns:
            Summary string.
        """
        if not data:
            return "No data available."

        lines = [f"Total rows: {len(data)}"]

        # Analyze numeric columns
        for col in data[0].keys():
            values = [row.get(col) for row in data if row.get(col) is not None]

            # Check if numeric
            numeric_values = []
            for v in values:
                try:
                    numeric_values.append(float(v))
                except (ValueError, TypeError):
                    continue

            if numeric_values and len(numeric_values) == len(values):
                lines.append(
                    f"{col}: min={min(numeric_values):.2f}, "
                    f"max={max(numeric_values):.2f}, "
                    f"avg={sum(numeric_values)/len(numeric_values):.2f}"
                )

        return "\n".join(lines)

    @staticmethod
    def to_markdown_table(data: List[Dict[str, Any]], max_rows: int = 50) -> str:
        """Convert results to Markdown table format.

        Args:
            data: List of result rows.
            max_rows: Maximum rows to display.

        Returns:
            Markdown table string.
        """
        if not data:
            return "No results found."

        columns = list(data[0].keys())
        display_data = data[:max_rows]

        lines = []

        # Header
        header = "| " + " | ".join(columns) + " |"
        lines.append(header)

        # Separator
        separator = "| " + " | ".join("---" for _ in columns) + " |"
        lines.append(separator)

        # Data rows
        for row in display_data:
            row_str = "| " + " | ".join(str(row.get(col, "")) for col in columns) + " |"
            lines.append(row_str)

        # Truncation notice
        if len(data) > max_rows:
            lines.append(f"\n*{len(data) - max_rows} more rows not shown*")

        return "\n".join(lines)

    @staticmethod
    def data_to_json_str(data: List[Dict[str, Any]], max_rows: int = 10) -> str:
        """Convert results to JSON string for LLM consumption.

        Args:
            data: List of result rows.
            max_rows: Maximum rows to include.

        Returns:
            JSON string.
        """
        import json

        if not data:
            return "[]"

        display_data = data[:max_rows]
        return json.dumps(display_data, ensure_ascii=False, indent=2, default=str)
