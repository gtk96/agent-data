"""Prompt template management for NL2SQL."""

from typing import Dict, List, Optional


class PromptManager:
    """Prompt template manager for NL2SQL.

    Contains system prompts and templates for SQL generation
    and result formatting.
    """

    SYSTEM_PROMPT = """You are a professional data analysis assistant. Your task is to generate SQL queries based on user's natural language questions.

## Rules
1. Only generate SELECT queries. INSERT/UPDATE/DELETE/DROP are not allowed.
2. Use standard SQL syntax (ANSI SQL), but adapt to the target database dialect.
3. Table and column names must exactly match the provided Schema (case-sensitive).
4. For fuzzy matching, use LIKE operator with % wildcards.
5. For date comparisons, use database native functions (e.g., strftime for SQLite, date_trunc for PostgreSQL).
6. Aggregation queries must include GROUP BY (unless aggregating the entire table).
7. Default LIMIT 100, unless user specifies a number.
8. When the question is ambiguous, generate the most reasonable query and explain assumptions in the explanation.

## Output Format
Output in strict JSON format with the following fields:
{
  "sql": "Generated SQL query",
  "explanation": "Brief explanation of the SQL (one sentence)",
  "tables_used": ["List of table names used"],
  "confidence": 0.95
}

Output only JSON, no other content. Do not wrap in markdown code blocks."""

    SQL_GENERATION_TEMPLATE = """## Database Schema

{schema_info}

## User Question

{question}

{conversation_context}

Please generate SQL query based on the above information."""

    RESULT_FORMAT_TEMPLATE = """You are a data analysis assistant. Please answer the user's question in natural language based on the following information.

## User Question
{question}

## Generated SQL
```sql
{sql}
```

## Query Result
{result_data}

## Requirements
1. Answer in clear, concise Chinese.
2. If the result contains numbers, highlight key data.
3. If the result is empty, explain possible reasons.
4. If there are multiple rows, summarize trends or rankings.
5. Keep the answer within 3 sentences.

Please provide your answer directly, without prefixes like "Based on the query results"."""

    FOLLOWUP_TEMPLATE = """## Conversation History
{history}

## Current Question
{question}

Please determine if the current question is independent or a follow-up. If it's a follow-up, combine the conversation history to understand the user's intent."""

    @classmethod
    def build_sql_generation_messages(
        cls,
        schema_info: str,
        question: str,
        conversation_context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Build messages for SQL generation.

        Args:
            schema_info: Formatted schema information.
            question: User's natural language question.
            conversation_context: Optional conversation history context.

        Returns:
            List of message dictionaries for LLM.
        """
        context = ""
        if conversation_context:
            context = f"## Conversation Context\n{conversation_context}\n"

        user_content = cls.SQL_GENERATION_TEMPLATE.format(
            schema_info=schema_info,
            question=question,
            conversation_context=context,
        )

        return [
            {"role": "system", "content": cls.SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    @classmethod
    def build_result_format_messages(
        cls,
        question: str,
        sql: str,
        result_data: str,
    ) -> List[Dict[str, str]]:
        """Build messages for result formatting.

        Args:
            question: Original user question.
            sql: Generated SQL query.
            result_data: Query result data as string.

        Returns:
            List of message dictionaries for LLM.
        """
        user_content = cls.RESULT_FORMAT_TEMPLATE.format(
            question=question,
            sql=sql,
            result_data=result_data,
        )

        return [
            {"role": "system", "content": "You are a helpful data analysis assistant."},
            {"role": "user", "content": user_content},
        ]
