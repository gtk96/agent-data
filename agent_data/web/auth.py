"""API Key authentication and role-based access control for NL2SQL web service.

Lightweight auth: API key + role (admin/user), stored in SQLite.
No external dependencies (uses stdlib hashlib + secrets + sqlite3).

Usage:
    from agent_data.web.auth import AuthManager, require_role

    auth = AuthManager(db_path="./data/auth.db")
    user = auth.create_user("alice", "secret", Role.USER)

    # In a route:
    ctx = auth.authenticate(request.headers.get("X-API-Key"))
    if not ctx:
        raise HTTPException(401, "Invalid API key")
    require_role(ctx, Role.ADMIN)  # raises 403 if insufficient
"""
import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException


class Role(str, Enum):
    """User roles."""
    USER = "user"          # read-only
    ADMIN = "admin"        # full access


@dataclass
class UserContext:
    """Authenticated user context, attached to request."""
    username: str
    role: Role
    api_key: str

    def is_admin(self) -> bool:
        return self.role == Role.ADMIN


@dataclass
class _User:
    """Internal user record."""
    username: str
    role: Role
    api_key: str
    created_at: float


class AuthManager:
    """SQLite-backed user and API key manager."""

    def __init__(self, db_path: str = "./data/auth.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                api_key TEXT NOT NULL UNIQUE,
                created_at REAL NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    @staticmethod
    def _generate_api_key() -> str:
        """Generate a cryptographically random API key."""
        return "im_" + secrets.token_urlsafe(32)

    def create_user(self, username: str, _password: str, role: Role = Role.USER) -> _User:
        """Create a new user. Auto-generates API key.

        Args:
            username: Unique username.
            _password: Reserved for future use (currently ignored, kept for API compat).
            role: User role (default USER).

        Returns:
            _User record with auto-generated api_key.

        Raises:
            ValueError: If username already exists.
        """
        import time
        api_key = self._generate_api_key()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO users (username, role, api_key, created_at) VALUES (?, ?, ?, ?)",
                (username, role.value, api_key, time.time()),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            raise ValueError(f"User '{username}' already exists")
        conn.close()
        return _User(username=username, role=role, api_key=api_key, created_at=time.time())

    def authenticate(self, api_key: Optional[str]) -> Optional[UserContext]:
        """Look up user by API key.

        Args:
            api_key: API key from request header (may be None).

        Returns:
            UserContext if found, None otherwise.
        """
        if not api_key:
            return None
        conn = self._conn()
        row = conn.execute(
            "SELECT username, role, api_key FROM users WHERE api_key = ?",
            (api_key,),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return UserContext(username=row[0], role=Role(row[1]), api_key=row[2])

    def list_users(self) -> List[UserContext]:
        """List all registered users."""
        conn = self._conn()
        rows = conn.execute("SELECT username, role, api_key FROM users ORDER BY created_at").fetchall()
        conn.close()
        return [UserContext(username=r[0], role=Role(r[1]), api_key=r[2]) for r in rows]

    def delete_user(self, username: str) -> bool:
        """Delete a user by username. Returns True if deleted."""
        conn = self._conn()
        cur = conn.execute("DELETE FROM users WHERE username = ?", (username,))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def hash_api_key(self, api_key: str) -> str:
        """Hash an API key for logging without exposing the secret."""
        return hashlib.sha256(api_key.encode()).hexdigest()[:12]


def require_role(ctx: UserContext, required: Role) -> None:
    """Dependency: raise 403 if ctx's role is insufficient.

    Usage:
        from fastapi import Depends
        @router.post(...)
        def route(ctx: UserContext = Depends(get_current_user)):
            require_role(ctx, Role.ADMIN)
            ...
    """
    # Role hierarchy: ADMIN > USER
    hierarchy = {Role.USER: 1, Role.ADMIN: 2}
    if hierarchy.get(ctx.role, 0) < hierarchy.get(required, 0):
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions: requires {required.value}, got {ctx.role.value}",
        )
