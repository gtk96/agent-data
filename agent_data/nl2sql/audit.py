"""NL2SQL SQL audit logging."""
import json
import time
from pathlib import Path


class SQLAuditor:
    """Writes structured JSON audit logs for each SQL execution."""

    def __init__(self, audit_dir: str = "./data/audit"):
        self._dir = Path(audit_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        session_id: str,
        sql: str,
        row_count: int,
        success: bool,
        query_time_ms: float,
        error: str = "",
    ) -> None:
        """Write one audit entry as a JSON file."""
        entry = {
            "ts": time.time(),
            "session_id": session_id,
            "sql": sql,
            "row_count": row_count,
            "success": success,
            "query_time_ms": round(query_time_ms, 2),
            "error": error,
        }
        path = self._dir / f"{int(time.time())}_{session_id[:8]}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)
