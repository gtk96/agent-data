"""Built-in connectors for Agent Data framework."""

import logging
from agent_data.core.connector import register_connector

logger = logging.getLogger(__name__)

# Import and register built-in connectors
# SQL connectors
try:
    from agent_data.connectors.sql import SQLConnector

    register_connector("sql", SQLConnector)
except ImportError as e:
    logger.debug(f"SQL connector not available: {e}")

# PostgreSQL connector
try:
    from agent_data.connectors.postgresql import PostgreSQLConnector

    register_connector("postgresql", PostgreSQLConnector)
except ImportError as e:
    logger.debug(f"PostgreSQL connector not available: {e}")

# Vector store connectors
try:
    from agent_data.connectors.vector import InMemoryVectorConnector

    register_connector("vector", InMemoryVectorConnector)
except ImportError as e:
    logger.debug(f"Vector connector not available: {e}")

# Chroma connector
try:
    from agent_data.connectors.chroma import ChromaConnector

    register_connector("chroma", ChromaConnector)
except ImportError as e:
    logger.debug(f"Chroma connector not available: {e}")

# Qdrant connector
try:
    from agent_data.connectors.qdrant import QdrantConnector

    register_connector("qdrant", QdrantConnector)
except ImportError as e:
    logger.debug(f"Qdrant connector not available: {e}")

# Pinecone connector
try:
    from agent_data.connectors.pinecone import PineconeConnector

    register_connector("pinecone", PineconeConnector)
except ImportError as e:
    logger.debug(f"Pinecone connector not available: {e}")

# REST API connector
try:
    from agent_data.connectors.rest_api import RESTAPIConnector

    register_connector("rest_api", RESTAPIConnector)
except ImportError as e:
    logger.debug(f"REST API connector not available: {e}")

# File connectors
try:
    from agent_data.connectors.file import FileConnector

    register_connector("file", FileConnector)
except ImportError as e:
    logger.debug(f"File connector not available: {e}")

__all__ = [
    "SQLConnector",
    "PostgreSQLConnector",
    "InMemoryVectorConnector",
    "ChromaConnector",
    "RESTAPIConnector",
    "FileConnector",
]
