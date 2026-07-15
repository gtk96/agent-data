"""NL2SQL core engine."""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agent_data.core.models import Query, QueryResult, QueryType
from agent_data.llm.base import BaseLLM, Message
from agent_data.nl2sql.audit import SQLAuditor
from agent_data.core.redact import redact_pii
from agent_data.nl2sql.formatter import ResultFormatter
from agent_data.nl2sql.memory import ConversationMemory, ConversationTurn, SQLiteConversationMemory
from agent_data.nl2sql.prompt import PromptManager
from agent_data.nl2sql.schema_manager import SchemaManager
from agent_data.nl2sql.semantic import SemanticLayer
from agent_data.nl2sql.validator import SQLValidator, ValidatorConfig

logger = logging.getLogger(__name__)


class LLMResponseParseError(Exception):
    """Raised when LLM response cannot be parsed into a structured SQL payload.

    Carries the raw response text so callers can log it for debugging
    or feed it into a corrective retry prompt.
    """

    def __init__(self, message: str, raw_response: str = ""):
        full = message if not raw_response else f"{message} Raw: {raw_response!r}"
        super().__init__(full)
        self.raw_response = raw_response


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
    input_tokens: int = 0
    output_tokens: int = 0


class NL2SQLEngine:
    """Text-to-SQL core engine.

    Orchestrates the complete flow: question → SQL → query → answer.
    """

    def __init__(
        self,
        llm: BaseLLM,
        connector,
        config: Optional[Dict[str, Any]] = None,
        tracer=None,
    ):
        """Initialize NL2SQL engine.

        Args:
            llm: LLM instance for text generation.
            connector: Database connector (BaseConnector).
            config: Optional configuration dictionary.
            tracer: Optional BaseTracer for OTel pipeline tracing.
        """
        self.llm = llm
        self.connector = connector
        self.config = NL2SQLConfig(**(config or {}))
        self.tracer = tracer

        self.schema_manager = SchemaManager(connector)
        self.validator = SQLValidator(
            ValidatorConfig(readonly=self.config.readonly, max_rows=self.config.max_rows)
        )
        self.memory = SQLiteConversationMemory(max_turns=self.config.max_turns)
        self.formatter = ResultFormatter()

        # Load business semantics from YAML if available
        semantic_dir = Path(__file__).parent / "semantic_defs"
        semantic_file = semantic_dir / "demo.yaml"
        self.semantic_layer = SemanticLayer(str(semantic_file)) if semantic_file.exists() else None

        # SQL audit logger
        self.auditor = SQLAuditor()

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
        start_time = time.monotonic()

        try:
            # 1. Get schema information
            schema_info = self.schema_manager.format_schema_with_semantics(self.semantic_layer)

            # 2. Get conversation context
            conversation_context = ""
            if self.config.enable_memory:
                conversation_context = self.memory.get_context_string(session_id)

            # 2.5. Resolve follow-up references if conversation exists
            resolved_question = question
            if conversation_context:
                resolved_question = await self._resolve_followup(
                    conversation_context, question
                )

            # 3. Generate SQL using LLM
            sql_result = await self._generate_sql(
                question=resolved_question,
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
            query_result = await self._execute_sql(sql, session_id=session_id)
            data = query_result.data if query_result.data else []

            # 6. Format answer using LLM
            data = redact_pii(data)
            # Save generate-phase tokens before _format_answer overwrites them
            generate_input_tokens = self._last_input_tokens
            generate_output_tokens = self._last_output_tokens
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
                input_tokens=generate_input_tokens + self._last_input_tokens,
                output_tokens=generate_output_tokens + self._last_output_tokens,
            )

        except LLMResponseParseError as e:
            logger.error(f"LLM response could not be parsed: {e}")
            query_time_ms = (time.monotonic() - start_time) * 1000
            preview = (e.raw_response or "")[:300]
            return NL2SQLResult(
                question=question,
                sql="",
                explanation=f"LLM response parse error: {e}",
                answer=(
                    "I couldn't generate a valid SQL query. "
                    "The model returned an unexpected response. "
                    f"Raw response (truncated): {preview!r}"
                ),
                confidence=0.0,
                session_id=session_id,
                query_time_ms=query_time_ms,
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
        """Generate SQL using LLM with one corrective retry on parse failure.

        Args:
            question: User's question.
            schema_info: Formatted schema information.
            conversation_context: Conversation history context.

        Returns:
            Dictionary with sql, explanation, tables_used, confidence.

        Raises:
            LLMResponseParseError: If the LLM fails to return a parseable
                SQL payload after the initial attempt and one retry.
        """
        messages = PromptManager.build_sql_generation_messages(
            schema_info=schema_info,
            question=question,
            conversation_context=conversation_context,
        )
        llm_messages = [Message(role=m["role"], content=m["content"]) for m in messages]

        for attempt in range(2):
            response = await self.llm.complete(llm_messages)
            content = response.content.strip()
            # Track token usage across both LLM calls
            self._last_input_tokens = response.usage.prompt_tokens
            self._last_output_tokens = response.usage.completion_tokens
            logger.info(
                f"=== LLM RAW RESPONSE (attempt {attempt + 1}) ===\n" f"{content}\n=== END ==="
            )
            try:
                result = self._parse_llm_response(content)
                logger.info(f"=== PARSED RESULT ===\n{result}\n=== END ===")
                return result
            except LLMResponseParseError as exc:
                if attempt == 0:
                    logger.warning(
                        "LLM response was not parseable; retrying with corrective prompt"
                    )
                    llm_messages = self._build_retry_messages(question, exc.raw_response)
                else:
                    logger.error(
                        f"LLM response still not parseable after retry: {exc.raw_response[:200]}"
                    )
                    raise

    async def _resolve_followup(
        self, conversation_context: str, question: str
    ) -> str:
        """Detect follow-up references and rewrite the question to be explicit.

        Uses a lightweight LLM call to resolve pronouns (他/它/她/这个/那个)
        and references (上一个/上次/前面) to concrete entities from the
        conversation history.

        Args:
            conversation_context: Formatted conversation history from memory.
            question: Current user question that may contain references.

        Returns:
            Rewritten self-contained question. Falls back to original on failure.
        """
        try:
            messages = PromptManager.build_followup_resolve_messages(
                history=conversation_context,
                question=question,
            )
            llm_messages = [Message(role=m["role"], content=m["content"]) for m in messages]
            response = await self.llm.complete(llm_messages, max_tokens=200)
            resolved = response.content.strip()

            # Safety: if LLM returns garbage or too long, keep original
            if not resolved or len(resolved) > len(question) * 3:
                return question

            logger.info(f"Follow-up resolved: {question!r} -> {resolved!r}")
            return resolved

        except Exception as e:
            logger.warning(f"Follow-up resolution failed, using original: {e}")
            return question

    def _build_retry_messages(self, question: str, previous_response: str) -> List[Message]:
        """Build a corrective retry prompt that pushes the LLM to emit JSON.

        Args:
            question: Original user question.
            previous_response: The unparseable LLM response, included so
                the model can see what it produced and self-correct.

        Returns:
            List of messages to send to the LLM for the retry attempt.
        """
        corrective_system = (
            "Your previous response did not follow the required JSON output format. "
            "You must respond with ONLY a single JSON object — no prose, no "
            "markdown fence, no explanation outside the JSON. The JSON must "
            "include a non-empty 'sql' field (string), plus optional "
            "'explanation', 'tables_used', and 'confidence' fields. "
            "If the question cannot be answered, return "
            '{"sql": "", "explanation": "<reason>"}.'
        )
        return [
            Message(role="system", content=corrective_system),
            Message(role="user", content=f"Question: {question}"),
            Message(
                role="user",
                content=(
                    "Your previous (invalid) response was:\n"
                    f"{previous_response}\n"
                    "Respond again, in valid JSON only."
                ),
            ),
        ]

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """Parse LLM response into a structured SQL payload.

        Strictly returns a dict with a non-empty ``sql`` field. Raises
        :class:`LLMResponseParseError` if the response is empty, has no SQL,
        or otherwise cannot be parsed. Never silently produces empty SQL.

        Args:
            content: Raw LLM response content.

        Returns:
            Dictionary with at least ``sql`` (str), ``explanation`` (str),
            ``tables_used`` (list), and ``confidence`` (float).

        Raises:
            LLMResponseParseError: If the response cannot be parsed.
        """
        import re

        raw = (content or "").strip()
        if not raw:
            raise LLMResponseParseError("LLM returned an empty response", raw)

        def _coerce(parsed: Any) -> Optional[Dict[str, Any]]:
            """Validate that parsed JSON is a dict with a non-empty 'sql' key."""
            if not isinstance(parsed, dict):
                return None
            sql = parsed.get("sql")
            if not isinstance(sql, str) or not sql.strip():
                return None
            return {
                "sql": sql.strip().rstrip(";"),
                "explanation": str(parsed.get("explanation", "")).strip(),
                "tables_used": list(parsed.get("tables_used") or []),
                "confidence": float(parsed.get("confidence", 0.0) or 0.0),
            }

        # 1. JSON in markdown code block
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if json_match:
            try:
                coerced = _coerce(json.loads(json_match.group(1)))
                if coerced is not None:
                    return coerced
            except json.JSONDecodeError:
                pass

        # 2. First balanced JSON object that contains a sql key
        for match in re.finditer(r"\{", raw):
            start = match.start()
            depth = 0
            for i in range(start, len(raw)):
                if raw[i] == "{":
                    depth += 1
                elif raw[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            coerced = _coerce(json.loads(raw[start : i + 1]))
                            if coerced is not None:
                                return coerced
                        except json.JSONDecodeError:
                            pass
                        break

        # 3. Entire content is JSON
        try:
            coerced = _coerce(json.loads(raw))
            if coerced is not None:
                return coerced
        except json.JSONDecodeError:
            pass

        raise LLMResponseParseError(
            "LLM response did not contain a parseable SQL payload "
            "(expected JSON with a 'sql' field).",
            raw,
        )

    async def _execute_sql(self, sql: str, session_id: str = "default") -> QueryResult:
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
        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                self.connector.execute(query),
                timeout=self.config.timeout_seconds,
            )
            elapsed = (time.monotonic() - start) * 1000
            row_count = len(result.data) if result.data else 0
            self.auditor.log(
                session_id=session_id,
                sql=sql,
                row_count=row_count,
                success=True,
                query_time_ms=elapsed,
            )
            return result
        except asyncio.TimeoutError:
            elapsed = (time.monotonic() - start) * 1000
            self.auditor.log(
                session_id=session_id,
                sql=sql,
                row_count=0,
                success=False,
                query_time_ms=elapsed,
                error="timeout",
            )
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
        # Track format-answer token usage
        self._last_input_tokens = response.usage.prompt_tokens
        self._last_output_tokens = response.usage.completion_tokens

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
