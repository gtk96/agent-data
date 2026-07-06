"""Built-in connectors for Agent Data framework."""

from agent_data.core.connector import register_connector

# Import and register built-in connectors
# SQL connectors
try:
    from agent_data.connectors.sql import SQLConnector

    register_connector("sql", SQLConnector)
except ImportError:
    pass

# PostgreSQL connector
try:
    from agent_data.connectors.postgresql import PostgreSQLConnector

    register_connector("postgresql", PostgreSQLConnector)
except ImportError:
    pass

# Vector store connectors
try:
    from agent_data.connectors.vector import InMemoryVectorConnector

    register_connector("vector", InMemoryVectorConnector)
except ImportError:
    pass

# Chroma connector
try:
    from agent_data.connectors.chroma import ChromaConnector

    register_connector("chroma", ChromaConnector)
except ImportError:
    pass

# Qdrant connector
try:
    from agent_data.connectors.qdrant import QdrantConnector

    register_connector("qdrant", QdrantConnector)
except ImportError:
    pass

# Pinecone connector
try:
    from agent_data.connectors.pinecone import PineconeConnector

    register_connector("pinecone", PineconeConnector)
except ImportError:
    pass

# REST API connector
try:
    from agent_data.connectors.rest_api import RESTAPIConnector

    register_connector("rest_api", RESTAPIConnector)
except ImportError:
    pass

# File connectors
try:
    from agent_data.connectors.file import FileConnector

    register_connector("file", FileConnector)
except ImportError:
    pass

__all__ = [
    "SQLConnector",
    "PostgreSQLConnector",
    "InMemoryVectorConnector",
    "ChromaConnector",
    "RESTAPIConnector",
    "FileConnector",
]
