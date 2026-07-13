"""Tests for Web API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


class TestWebAPI:
    """Tests for Web API endpoints."""

    @pytest.fixture
    def mock_engine(self):
        """Create mock NL2SQL engine."""
        engine = MagicMock()
        engine.query = AsyncMock()
        engine.health_check = AsyncMock(
            return_value={
                "llm": True,
                "database": True,
                "overall": True,
            }
        )
        engine.validator = MagicMock()
        engine.validator.validate = MagicMock(return_value=(True, None))
        engine.connector = MagicMock()
        engine.connector.execute = AsyncMock()
        engine.connector.health_check = AsyncMock(return_value=True)
        engine.memory = MagicMock()
        engine.memory.get_history = MagicMock(return_value=[])
        engine.clear_session = MagicMock()

        # Mock schema manager
        engine.schema_manager = MagicMock()
        engine.schema_manager.get_schema = AsyncMock(
            return_value={
                "users": MagicMock(
                    name="users",
                    comment="User table",
                    columns=[],
                    row_count=100,
                )
            }
        )

        return engine

    @pytest.fixture
    def client(self, mock_engine):
        """Create test client with mock engine."""
        from agent_data.web.app import create_app

        app = create_app(engine=mock_engine)
        return TestClient(app)

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["llm"] is True
        assert data["database"] is True

    def test_list_data_sources(self, client):
        """Test list data sources endpoint."""
        response = client.get("/api/v1/datasources")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_schema(self, client):
        """Test get schema endpoint."""
        response = client.get("/api/v1/schema/default")
        assert response.status_code == 200

    def test_get_history(self, client):
        """Test get history endpoint."""
        response = client.get("/api/v1/history/test-session")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session"
        assert isinstance(data["turns"], list)

    def test_clear_history(self, client):
        """Test clear history endpoint."""
        response = client.delete("/api/v1/history/test-session")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cleared"
