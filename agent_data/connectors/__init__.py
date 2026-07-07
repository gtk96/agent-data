"""Built-in connectors for Agent Data framework."""

import logging

from agent_data.core.connector import list_connectors, register_connector

logger = logging.getLogger(__name__)


def available_connectors():
    """Return names of connectors that successfully registered.

    Useful for diagnostics — when ``get_connector(name)`` returns ``None``,
    call this to see what is actually available in the current environment.
    """
    return list_connectors()


__all__ = [
    "available_connectors",
    "SQLConnector",
    "PostgreSQLConnector",
    "InMemoryVectorConnector",
    "ChromaConnector",
    "QdrantConnector",
    "PineconeConnector",
    "RESTAPIConnector",
    "FileConnector",
]

# Import and register built-in connectors.
# Optional-dependency missing is logged at WARNING (not DEBUG) so users notice
# why a feature they expected isn't available.

# SQL connectors
try:
    from agent_data.connectors.sql import SQLConnector

    register_connector("sql", SQLConnector)
except ImportError as e:
    logger.warning("SQL connector not available: %s", e)

# PostgreSQL connector
try:
    from agent_data.connectors.postgresql import PostgreSQLConnector

    register_connector("postgresql", PostgreSQLConnector)
except ImportError as e:
    logger.warning("PostgreSQL connector not available: %s", e)

# Vector store connectors
try:
    from agent_data.connectors.vector import InMemoryVectorConnector

    register_connector("vector", InMemoryVectorConnector)
except ImportError as e:
    logger.warning("Vector connector not available: %s", e)

# Chroma connector
try:
    from agent_data.connectors.chroma import ChromaConnector

    register_connector("chroma", ChromaConnector)
except ImportError as e:
    logger.warning("Chroma connector not available: %s", e)

# Qdrant connector
try:
    from agent_data.connectors.qdrant import QdrantConnector

    register_connector("qdrant", QdrantConnector)
except ImportError as e:
    logger.warning("Qdrant connector not available: %s", e)

# Pinecone connector
try:
    from agent_data.connectors.pinecone import PineconeConnector

    register_connector("pinecone", PineconeConnector)
except ImportError as e:
    logger.warning("Pinecone connector not available: %s", e)

# REST API connector
try:
    from agent_data.connectors.rest_api import RESTAPIConnector

    register_connector("rest_api", RESTAPIConnector)
except ImportError as e:
    logger.warning("REST API connector not available: %s", e)

# File connectors
try:
    from agent_data.connectors.file import FileConnector

    register_connector("file", FileConnector)
except ImportError as e:
    logger.warning("File connector not available: %s", e)
