"""NL2SQL (Natural Language to SQL) module for agent-data."""

from agent_data.nl2sql.engine import NL2SQLEngine, NL2SQLResult
from agent_data.nl2sql.memory import ConversationMemory, ConversationTurn
from agent_data.nl2sql.schema_manager import SchemaManager, TableInfo
from agent_data.nl2sql.validator import SQLValidator, ValidatorConfig

__all__ = [
    "NL2SQLEngine",
    "NL2SQLResult",
    "ConversationMemory",
    "ConversationTurn",
    "SchemaManager",
    "TableInfo",
    "SQLValidator",
    "ValidatorConfig",
]
