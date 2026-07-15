"""Business semantic layer — injects column-level definitions into LLM prompts."""
from pathlib import Path
from typing import Dict, List, Optional

import yaml


class SemanticLayer:
    """Loads business semantic definitions from YAML for LLM prompt injection."""

    def __init__(self, yaml_path: Optional[str] = None):
        self._defs: Dict[str, Dict] = {}
        if yaml_path:
            self.load(yaml_path)

    def load(self, path: str) -> None:
        """Load semantic definitions from a YAML file.

        Expected format:
            table_name:
              column_name: "business definition"
              column_name_2: "another definition"
        """
        with open(path, "r", encoding="utf-8") as f:
            self._defs = yaml.safe_load(f) or {}

    def get_column_semantic(self, table: str, column: str) -> str:
        """Return the business definition for a given table.column.

        Returns empty string if not found.
        """
        return self._defs.get(table, {}).get(column, "")

    def format_for_prompt(self, tables: Optional[List[str]] = None) -> str:
        """Format semantics as a text block for LLM prompt injection.

        Returns empty string if no definitions loaded.
        """
        if not self._defs:
            return ""

        lines = ["## Business Semantics", ""]
        target = tables if tables else list(self._defs.keys())

        for table in target:
            cols = self._defs.get(table, {})
            if not cols:
                continue
            lines.append(f"### {table}")
            for col, desc in cols.items():
                lines.append(f"  - {col}: {desc}")
            lines.append("")

        return "\n".join(lines) if len(lines) > 2 else ""
