"""NL2SQL core engine."""

import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agent_data.core.models import Query, QueryResult, QueryType
from agent_data.llm.base import BaseLLM, Message
from agent_data.nl2sql.formatter import ResultFormatter
from agent_data.nl2sql.memory import ConversationMemory, ConversationTurn
from agent_data.nl2sql.prompt import PromptManager
from agent_data.nl2sql.schema_manager import SchemaManager
from agent_data.nl2sql.validator import SQLValidator, ValidatorConfig

logger = logging.getLogger(__name__)


class NL2SQLConfig(BaseModel):
    """NL2SQL engine configuration."""

    max_rows: int = Field(default=100, gt=0, description="Maximum rows to return")
    timeout_seconds: int = Field(default=30, gt=0, description="Query timeout in seconds")
    enable_memory: bool = Field(default=True, description="Enable conversation memory")
    max_turns: int = Field(default=10, ge=1, description="Maximum conversation turns to remember")
    readonly: bool = Field(default=True, description="Read-only mode")


class NL2SQLResult(BaseModel):
    """NL2SQL complete result."""

    question: str
    sql: str
    explanation: str = ""
    data: List[Dict[str, Any]] = Field(default_factory=list)
    answer: str
    confidence: float = 0.0
    tables_used: List[str] = Field(default_factory=list)
    query_time_ms: float = 0.0
    session_id: str = "default"


class NL2SQLEngine:
    """Text-to-SQL core engine.

    Orchestrates the complete flow: question → SQL → query → answer.
    """

    def __init__(
        self,
        llm: BaseLLM,
        connector,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize NL2SQL engine.

        Args:
            llm: LLM instance for text generation.
            connector: Database connector (BaseConnector).
            config: Optional configuration dictionary.
        """
        self.llm = llm
        self.connector = connector
        self.config = NL2SQLConfig(**(config or {}))

        self.schema_manager = SchemaManager(connector)
        self.validator = SQLValidator(
            ValidatorConfig(readonly=self.config.readonly, max_rows=self.config.max_rows)
        )
        self.memory = ConversationMemory(max_turns=self.config.max_turns)
        self.formatter = ResultFormatter()

    async def query(
        self,
        question: str,
        session_id: str = "default",
    ) -> NL2SQLResult:
        """Execute the complete NL2SQL flow.

        Args:
            question: User's natural language question.
            session_id: Session identifier for conversation memory.

        Returns:
            NL2SQLResult with question, SQL, answer, and data.
        """
        import time

        start_time = time.monotonic()

        try:
            # 1. Get schema information
            schema_info = self.schema_manager.format_schema_for_prompt()

            # 2. Get conversation context
            conversation_context = ""
            if self.config.enable_memory:
                conversation_context = self.memory.get_context_string(session_id)

            # 3. Generate SQL using LLM
            sql_result = await self._generate_sql(
                question=question,
                schema_info=schema_info,
                conversation_context=conversation_context,
            )

            sql = sql_result.get("sql", "")
            explanation = sql_result.get("explanation", "")
            tables_used = sql_result.get("tables_used", [])
            confidence = sql_result.get("confidence", 0.0)

            # 4. Validate SQL
            is_valid, error = self.validator.validate(sql)
            if not is_valid:
                return NL2SQLResult(
                    question=question,
                    sql=sql,
                    explanation=f"SQL validation failed: {error}",
                    answer=f"Sorry, I couldn't generate a valid query: {error}",
                    confidence=0.0,
                    session_id=session_id,
                    query_time_ms=(time.monotonic() - start_time) * 1000,
                )

            # 5. Execute SQL query
            query_result = await self._execute_sql(sql)
            data = query_result.data if query_result.data else []

            # 6. Format answer using LLM
            answer = await self._format_answer(question, sql, data)

            # 7. Save to conversation memory
            if self.config.enable_memory:
                turn = ConversationTurn(
                    question=question,
                    sql=sql,
                    answer=answer,
                )
                self.memory.add_turn(session_id, turn)

            query_time_ms = (time.monotonic() - start_time) * 1000

            return NL2SQLResult(
                question=question,
                sql=sql,
                explanation=explanation,
                data=data,
                answer=answer,
                confidence=confidence,
                tables_used=tables_used,
                query_time_ms=query_time_ms,
                session_id=session_id,
            )

        except Exception as e:
            logger.error(f"NL2SQL query failed: {e}")
            query_time_ms = (time.monotonic() - start_time) * 1000
            return NL2SQLResult(
                question=question,
                sql="",
                explanation=f"Error: {str(e)}",
                answer=f"Sorry, an error occurred while processing your question: {str(e)}",
                confidence=0.0,
                session_id=session_id,
                query_time_ms=query_time_ms,
            )

    async def _generate_sql(
        self,
        question: str,
        schema_info: str,
        conversation_context: str,
    ) -> Dict[str, Any]:
        """Generate SQL using LLM.

        Args:
            question: User's question.
            schema_info: Formatted schema information.
            conversation_context: Conversation history context.

        Returns:
            Dictionary with sql, explanation, tables_used, confidence.
        """
        messages = PromptManager.build_sql_generation_messages(
            schema_info=schema_info,
            question=question,
            conversation_context=conversation_context,
        )

        llm_messages = [Message(role=m["role"], content=m["content"]) for m in messages]
        response = await self.llm.complete(llm_messages)

        # Parse JSON response
        content = response.content.strip()
        logger.info(f"=== LLM RAW RESPONSE ===\n{content}\n=== END ===")
        result = self._parse_llm_response(content)
        logger.info(f"=== PARSED RESULT ===\n{result}\n=== END ===")

        return result

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """Parse LLM response to extract SQL.

        Args:
            content: Raw LLM response content.

        Returns:
            Dictionary with sql, explanation, tables_used, confidence.
        """
        import re

        if not content:
            return {
                "sql": "",
                "explanation": "Empty LLM response",
                "tables_used": [],
                "confidence": 0.0,
            }

        # Try to extract JSON from response
        # 1. Try to find JSON block in markdown
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 2. Try to find balanced JSON object (handle nested braces)
        for match in re.finditer(r"\{", content):
            start = match.start()
            depth = 0
            for i in range(start, len(content)):
                if content[i] == "{":
                    depth += 1
                elif content[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            result = json.loads(content[start : i + 1])
                            if "sql" in result:
                                return result
                        except json.JSONDecodeError:
                            pass
                        break

        # 3. Try parsing entire content as JSON
        try:
            result = json.loads(content)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        # 4. Try to extract SQL from text
        sql_match = re.search(
            r"```(?:sql)?\s*(SELECT.*?)\s*```", content, re.DOTALL | re.IGNORECASE
        )
        if sql_match:
            return {
                "sql": sql_match.group(1).strip().rstrip(";"),
                "explanation": "",
                "tables_used": [],
                "confidence": 0.6,
            }

        # 5. Try to find SELECT statement directly
        sql_match = re.search(
            r"(SELECT\s+[\s\S]+?FROM\s+\w+[\s\S]*?)(?:;|$|\n\n)", content, re.IGNORECASE
        )
        if sql_match:
            return {
                "sql": sql_match.group(1).strip().rstrip(";"),
                "explanation": "Extracted SQL from text response",
                "tables_used": [],
                "confidence": 0.5,
            }

        # 6. Last resort - return whole content as explanation, no SQL
        logger.warning(f"Could not extract SQL from LLM response: {content[:200]}")
        return {
            "sql": "",
            "explanation": content,
            "tables_used": [],
            "confidence": 0.3,
        }

    async def _execute_sql(self, sql: str) -> QueryResult:
        """Execute SQL query.

        Args:
            sql: SQL query to execute.

        Returns:
            QueryResult with query results.
        """
        import asyncio

        # Add LIMIT if not present
        sql_upper = sql.upper().rstrip(";")
        if "LIMIT" not in sql_upper:
            sql = f"{sql.rstrip(';')} LIMIT {self.config.max_rows}"

        # Create query object
        query = Query(
            source="nl2sql",
            query_type=QueryType.SELECT,
            query=sql,
        )

        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                self.connector.execute(query),
                timeout=self.config.timeout_seconds,
            )
            return result
        except asyncio.TimeoutError:
            raise RuntimeError(f"Query timed out after {self.config.timeout_seconds} seconds")

    async def _format_answer(
        self,
        question: str,
        sql: str,
        result_data: List[Dict[str, Any]],
    ) -> str:
        """Format query results as natural language answer.

        Args:
            question: Original user question.
            sql: Generated SQL query.
            result_data: Query result data.

        Returns:
            Natural language answer.
        """
        # Format result data for LLM
        result_str = self.formatter.to_table_text(result_data, max_rows=10)

        messages = PromptManager.build_result_format_messages(
            question=question,
            sql=sql,
            result_data=result_str,
        )

        llm_messages = [Message(role=m["role"], content=m["content"]) for m in messages]
        response = await self.llm.complete(llm_messages)

        return response.content

    async def health_check(self) -> Dict[str, bool]:
        """Check health of all engine components.

        Returns:
            Dictionary with component health status.
        """
        # Check LLM health
        llm_ok = False
        if self.llm is not None:
            try:
                llm_ok = await self.llm.health_check()
            except Exception:
                llm_ok = False

        # Check database health
        db_ok = False
        try:
            await self.connector.health_check()
            db_ok = True
        except Exception:
            db_ok = False

        return {
            "llm": llm_ok,
            "database": db_ok,
            "overall": db_ok,  # Only database is required
        }

    def clear_session(self, session_id: str):
        """Clear conversation memory for a session.

        Args:
            session_id: Session identifier to clear.
        """
        self.memory.clear_session(session_id)
