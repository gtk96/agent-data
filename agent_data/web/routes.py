"""API routes for web service."""

import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request

from agent_data.nl2sql.engine import NL2SQLEngine
from agent_data.nl2sql.history import QueryHistoryItem, QueryHistoryStorage
from agent_data.web.schemas import (
    DataSourceInfo,
    HealthResponse,
    HistoryResponse,
    NL2SQLQueryRequest,
    NL2SQLQueryResponse,
    QueryHistoryItemResponse,
    QueryHistoryRequest,
    QueryHistoryResponse,
    QueryHistoryStatsResponse,
    QueryRequest,
    QueryResponse,
    SchemaResponse,
    SqlExecuteRequest,
    SqlExecuteResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["nl2sql"])


def get_engine(request: Request) -> NL2SQLEngine:
    """Get NL2SQL engine from app state."""
    return request.app.state.engine


@router.post("/v1/chat/completions", response_model=QueryResponse)
async def chat_completions(request: QueryRequest, req: Request):
    """OpenAI-compatible chat completions endpoint.

    This is the main endpoint used by NextChat frontend.
    """
    engine = get_engine(req)

    # Extract user message
    user_message = ""
    for msg in request.messages:
        if msg.get("role") == "user":
            user_message = msg.get("content", "")

    if not user_message:
        raise HTTPException(status_code=400, detail="No user message found")

    # Use session_id from request or generate one
    session_id = request.session_id or str(uuid.uuid4())

    # Execute NL2SQL query
    result = await engine.query(question=user_message, session_id=session_id)

    # Build response in OpenAI format
    response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())

    # Format answer with SQL if available
    content = result.answer
    if result.sql:
        content += f"\n\n**Generated SQL:**\n```sql\n{result.sql}\n```"

    return QueryResponse(
        id=response_id,
        created=created,
        model=request.model,
        choices=[
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        usage={
            "prompt_tokens": 0,
            "completion_tokens": len(content.split()),
            "total_tokens": len(content.split()),
        },
    )


@router.post("/api/v1/query", response_model=NL2SQLQueryResponse)
async def nl2sql_query(request: NL2SQLQueryRequest, req: Request):
    """NL2SQL specific query endpoint with detailed response."""
    engine = get_engine(req)

    session_id = request.session_id or str(uuid.uuid4())

    result = await engine.query(question=request.question, session_id=session_id)

    # Extract columns from data
    columns = []
    if result.data:
        columns = list(result.data[0].keys())

    return NL2SQLQueryResponse(
        session_id=result.session_id,
        question=result.question,
        sql=result.sql if request.show_sql else None,
        explanation=result.explanation,
        answer=result.answer,
        data=result.data,
        columns=columns,
        row_count=len(result.data),
        confidence=result.confidence,
        query_time_ms=result.query_time_ms,
    )


@router.get("/api/v1/schema/{data_source}", response_model=SchemaResponse)
async def get_schema(data_source: str, req: Request):
    """Get schema information for a data source."""
    engine = get_engine(req)

    try:
        schema = await engine.schema_manager.get_schema()
        tables = []
        for name, table_info in schema.items():
            tables.append(
                {
                    "name": name,
                    "comment": table_info.comment,
                    "columns": [
                        {
                            "name": col.name,
                            "type": col.type,
                            "primary_key": col.primary_key,
                        }
                        for col in table_info.columns
                    ],
                    "row_count": table_info.row_count,
                }
            )
        return SchemaResponse(tables=tables)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/history/{session_id}", response_model=HistoryResponse)
async def get_history(session_id: str, req: Request):
    """Get conversation history for a session."""
    engine = get_engine(req)

    history = engine.memory.get_history(session_id)
    turns = [
        {
            "question": turn.question,
            "sql": turn.sql,
            "answer": turn.answer,
            "timestamp": turn.timestamp,
        }
        for turn in history
    ]

    return HistoryResponse(session_id=session_id, turns=turns)


@router.delete("/api/v1/history/{session_id}")
async def clear_history(session_id: str, req: Request):
    """Clear conversation history for a session."""
    engine = get_engine(req)
    engine.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}


@router.get("/api/v1/datasources")
async def list_data_sources(req: Request):
    """List available data sources."""

    # Get data sources from engine's connector
    data_sources = [
        DataSourceInfo(
            name="default",
            type="sql",
            description="Default data source",
            status="active",
        )
    ]

    return [ds.model_dump() for ds in data_sources]


@router.get("/api/v1/health", response_model=HealthResponse)
async def health_check(req: Request):
    """Health check endpoint."""
    engine = req.app.state.engine

    if engine is None:
        return HealthResponse(
            status="no_engine",
            llm=False,
            database=False,
            version="0.1.0",
        )

    health = await engine.health_check()

    return HealthResponse(
        status="healthy" if health["overall"] else "degraded",
        llm=health["llm"],
        database=health["database"],
        version="0.1.0",
    )


@router.post("/api/v1/sql/execute", response_model=SqlExecuteResponse)
async def execute_sql(request: SqlExecuteRequest, req: Request):
    """Execute SQL query directly.

    This endpoint allows executing SQL queries directly,
    useful for debugging and manual queries.
    """
    engine = get_engine(req)

    # Validate SQL
    is_valid, error = engine.validator.validate(request.sql)
    if not is_valid:
        return SqlExecuteResponse(
            success=False,
            error=f"SQL validation failed: {error}",
            sql=request.sql,
        )

    try:
        # Execute SQL directly using connector's connection
        import asyncio
        import time

        # Add LIMIT if not present
        sql = request.sql.rstrip(";")
        if "LIMIT" not in sql.upper():
            sql = f"{sql} LIMIT {request.max_rows or 100}"

        start_time = time.time()

        # Execute query directly on the connector's connection
        def execute_sync():
            if not engine.connector._connection:
                raise RuntimeError("Not connected to database")
            cursor = engine.connector._connection.execute(sql)
            rows = cursor.fetchall()
            columns = (
                [description[0] for description in cursor.description] if cursor.description else []
            )
            return [dict(zip(columns, row)) for row in rows]

        data = await asyncio.wait_for(
            asyncio.to_thread(execute_sync),
            timeout=request.timeout or 30,
        )

        query_time_ms = (time.time() - start_time) * 1000

        # Extract columns
        columns = []
        if data:
            columns = list(data[0].keys())

        return SqlExecuteResponse(
            success=True,
            sql=sql,
            data=data,
            columns=columns,
            row_count=len(data),
            query_time_ms=query_time_ms,
        )

    except asyncio.TimeoutError:
        return SqlExecuteResponse(
            success=False,
            error=f"Query timed out after {request.timeout or 30} seconds",
            sql=request.sql,
        )
    except Exception as e:
        logger.error(f"SQL execution failed: {e}")
        return SqlExecuteResponse(
            success=False,
            error=str(e),
            sql=request.sql,
        )


# Query History Storage
def get_history_storage(req: Request) -> QueryHistoryStorage:
    """Get history storage from app state."""
    if not hasattr(req.app.state, "history_storage"):
        req.app.state.history_storage = QueryHistoryStorage()
    return req.app.state.history_storage


@router.post("/api/v1/history/save", response_model=QueryHistoryItemResponse)
async def save_query_history(request: QueryHistoryRequest, req: Request):
    """Save a query to history.

    This endpoint saves a query (question + SQL + result) to history.
    """
    storage = get_history_storage(req)

    item = QueryHistoryItem(
        id="",
        question=request.question,
        sql=request.sql,
        answer=request.answer,
        data=request.data or [],
        columns=request.columns or [],
        row_count=request.row_count or 0,
        query_time_ms=request.query_time_ms or 0.0,
        session_id=request.session_id or "default",
        tags=request.tags or [],
    )

    saved_item = storage.add_item(item)

    return QueryHistoryItemResponse(
        id=saved_item.id,
        question=saved_item.question,
        sql=saved_item.sql,
        answer=saved_item.answer,
        data=saved_item.data,
        columns=saved_item.columns,
        row_count=saved_item.row_count,
        query_time_ms=saved_item.query_time_ms,
        timestamp=saved_item.timestamp,
        session_id=saved_item.session_id,
        favorite=saved_item.favorite,
        tags=saved_item.tags,
    )


@router.get("/api/v1/history/list", response_model=QueryHistoryResponse)
async def list_query_history(
    session_id: str = "default",
    limit: int = 50,
    offset: int = 0,
    favorite_only: bool = False,
    req: Request = None,
):
    """List query history for a session.

    This endpoint returns a list of query history items.
    """
    storage = get_history_storage(req)

    items = storage.get_history(
        session_id=session_id,
        limit=limit,
        offset=offset,
        favorite_only=favorite_only,
    )

    return QueryHistoryResponse(
        session_id=session_id,
        items=[
            QueryHistoryItemResponse(
                id=item.id,
                question=item.question,
                sql=item.sql,
                answer=item.answer,
                data=item.data,
                columns=item.columns,
                row_count=item.row_count,
                query_time_ms=item.query_time_ms,
                timestamp=item.timestamp,
                session_id=item.session_id,
                favorite=item.favorite,
                tags=item.tags,
            )
            for item in items
        ],
        total=len(items),
    )


@router.get("/api/v1/history/item/{item_id}", response_model=QueryHistoryItemResponse)
async def get_query_history_item(
    item_id: str,
    session_id: str = "default",
    req: Request = None,
):
    """Get a specific query history item.

    This endpoint returns a single history item by ID.
    """
    storage = get_history_storage(req)

    item = storage.get_item(session_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="History item not found")

    return QueryHistoryItemResponse(
        id=item.id,
        question=item.question,
        sql=item.sql,
        answer=item.answer,
        data=item.data,
        columns=item.columns,
        row_count=item.row_count,
        query_time_ms=item.query_time_ms,
        timestamp=item.timestamp,
        session_id=item.session_id,
        favorite=item.favorite,
        tags=item.tags,
    )


@router.put("/api/v1/history/favorite/{item_id}")
async def toggle_favorite(
    item_id: str,
    session_id: str = "default",
    req: Request = None,
):
    """Toggle favorite status of a history item.

    This endpoint toggles the favorite status of a history item.
    """
    storage = get_history_storage(req)

    item = storage.toggle_favorite(session_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="History item not found")

    return {
        "status": "updated",
        "id": item.id,
        "favorite": item.favorite,
    }


@router.delete("/api/v1/history/item/{item_id}")
async def delete_query_history_item(
    item_id: str,
    session_id: str = "default",
    req: Request = None,
):
    """Delete a query history item.

    This endpoint deletes a history item by ID.
    """
    storage = get_history_storage(req)

    deleted = storage.delete_item(session_id, item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="History item not found")

    return {"status": "deleted", "id": item_id}


@router.get("/api/v1/history/search", response_model=QueryHistoryResponse)
async def search_query_history(
    q: str,
    session_id: str = "default",
    limit: int = 50,
    req: Request = None,
):
    """Search query history.

    This endpoint searches history items by question or SQL.
    """
    storage = get_history_storage(req)

    items = storage.search(session_id, q, limit)

    return QueryHistoryResponse(
        session_id=session_id,
        items=[
            QueryHistoryItemResponse(
                id=item.id,
                question=item.question,
                sql=item.sql,
                answer=item.answer,
                data=item.data,
                columns=item.columns,
                row_count=item.row_count,
                query_time_ms=item.query_time_ms,
                timestamp=item.timestamp,
                session_id=item.session_id,
                favorite=item.favorite,
                tags=item.tags,
            )
            for item in items
        ],
        total=len(items),
    )


@router.get("/api/v1/history/stats", response_model=QueryHistoryStatsResponse)
async def get_query_history_stats(
    session_id: str = "default",
    req: Request = None,
):
    """Get query history statistics.

    This endpoint returns statistics about query history.
    """
    storage = get_history_storage(req)

    stats = storage.get_stats(session_id)

    return QueryHistoryStatsResponse(
        session_id=session_id,
        total_queries=stats["total_queries"],
        favorite_count=stats["favorite_count"],
        avg_query_time_ms=stats["avg_query_time_ms"],
    )
