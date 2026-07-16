"""Tests for API Key authentication and role-based access control."""
import os
import tempfile
import pytest
from fastapi import HTTPException
from agent_data.web.auth import AuthManager, UserContext, require_role, Role


def test_create_user():
    with tempfile.TemporaryDirectory() as d:
        auth = AuthManager(db_path=os.path.join(d, "auth.db"))
        user = auth.create_user("alice", "secret123", Role.USER)
        assert user.username == "alice"
        assert user.role == Role.USER
        assert user.api_key  # auto-generated


def test_create_user_with_admin():
    with tempfile.TemporaryDirectory() as d:
        auth = AuthManager(db_path=os.path.join(d, "auth.db"))
        user = auth.create_user("admin1", "pass", Role.ADMIN)
        assert user.role == Role.ADMIN


def test_create_user_duplicate():
    with tempfile.TemporaryDirectory() as d:
        auth = AuthManager(db_path=os.path.join(d, "auth.db"))
        auth.create_user("alice", "pass")
        with pytest.raises(ValueError):
            auth.create_user("alice", "pass2")


def test_authenticate_by_api_key():
    with tempfile.TemporaryDirectory() as d:
        auth = AuthManager(db_path=os.path.join(d, "auth.db"))
        user = auth.create_user("alice", "pass", Role.ADMIN)
        ctx = auth.authenticate(user.api_key)
        assert ctx is not None
        assert ctx.username == "alice"
        assert ctx.role == Role.ADMIN


def test_authenticate_wrong_key():
    with tempfile.TemporaryDirectory() as d:
        auth = AuthManager(db_path=os.path.join(d, "auth.db"))
        ctx = auth.authenticate("invalid_key_12345")
        assert ctx is None


def test_require_role_admin():
    ctx = UserContext(username="admin1", role=Role.ADMIN, api_key="k1")
    # admin can access everything
    require_role(ctx, Role.USER)
    require_role(ctx, Role.ADMIN)


def test_require_role_user_blocked():
    ctx = UserContext(username="user1", role=Role.USER, api_key="k1")
    require_role(ctx, Role.USER)
    with pytest.raises(HTTPException) as exc_info:
        require_role(ctx, Role.ADMIN)
    assert exc_info.value.status_code == 403


def test_generate_api_key_unique():
    with tempfile.TemporaryDirectory() as d:
        auth = AuthManager(db_path=os.path.join(d, "auth.db"))
        k1 = auth._generate_api_key()
        k2 = auth._generate_api_key()
        assert k1 != k2
        assert len(k1) >= 32


def test_list_users():
    with tempfile.TemporaryDirectory() as d:
        auth = AuthManager(db_path=os.path.join(d, "auth.db"))
        auth.create_user("alice", "p", Role.USER)
        auth.create_user("bob", "p", Role.ADMIN)
        users = auth.list_users()
        assert len(users) == 2
        usernames = {u.username for u in users}
        assert usernames == {"alice", "bob"}


def test_delete_user():
    with tempfile.TemporaryDirectory() as d:
        auth = AuthManager(db_path=os.path.join(d, "auth.db"))
        user = auth.create_user("alice", "p", Role.USER)
        assert auth.delete_user("alice") is True
        assert auth.authenticate(user.api_key) is None
        assert auth.delete_user("nonexistent") is False
