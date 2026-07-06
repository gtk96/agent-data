"""
LangChain integration for Agent Data framework.
"""

from typing import Any, Dict, List, Optional, Type

from agent_data.core.client import AgentDataClient
from agent_data.core.models import Query, QueryFilter, QueryType

try:
    from langchain.tools import BaseTool
    from langchain.callbacks.manager import CallbackManagerForToolRun
    from pydantic import Field

    class AgentDataTool(BaseTool):
        """LangChain tool for querying data sources via Agent Data framework."""

        name: str = "agent_data_query"
        description: str = (
            "Query data sources to get information. "
            "Use this tool when you need to access databases, vector stores, "
            "or other data sources to answer user questions."
        )

        client: AgentDataClient = Field(exclude=True)

        class Config:
            arbitrary_types_allowed = True

        def __init__(self, client: AgentDataClient, **kwargs):
            super().__init__(client=client, **kwargs)

        def _run(
            self,
            query: str,
            source: Optional[str] = None,
            query_type: str = "search",
            filters: Optional[str] = None,
            limit: int = 10,
            run_manager: Optional[CallbackManagerForToolRun] = None,
        ) -> str:
            """Run the tool synchronously."""
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, we need to create a new task
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        result = pool.submit(
                            asyncio.run,
                            self._arun(query, source, query_type, filters, limit),
                        ).result()
                else:
                    result = loop.run_until_complete(
                        self._arun(query, source, query_type, filters, limit)
                    )
            except RuntimeError:
                result = asyncio.run(self._arun(query, source, query_type, filters, limit))

            return result

        async def _arun(
            self,
            query: str,
            source: Optional[str] = None,
            query_type: str = "search",
            filters: Optional[str] = None,
            limit: int = 10,
            run_manager: Optional[CallbackManagerForToolRun] = None,
        ) -> str:
            """Run the tool asynchronously."""
            try:
                # Build query object
                try:
                    qt = QueryType(query_type)
                except ValueError:
                    qt = QueryType.SEARCH

                # Parse filters if provided
                query_filters = []
                if filters:
                    # Simple filter parsing: "field=value,field2=value2"
                    for filter_str in filters.split(","):
                        if "=" in filter_str:
                            field, value = filter_str.split("=", 1)
                            query_filters.append(
                                QueryFilter(field=field.strip(), operator="eq", value=value.strip())
                            )

                # Build query
                q = Query(
                    source=source or "default",
                    query_type=qt,
                    query=query,
                    filters=query_filters,
                    limit=limit,
                )

                # Execute query
                result = await self.client.query(q)

                if result.error:
                    return f"Error: {result.error}"

                # Format result
                if not result.data:
                    return "No results found."

                # Convert to readable format
                output_lines = []
                for i, item in enumerate(result.data[:limit], 1):
                    output_lines.append(f"{i}. {item}")

                return "\n".join(output_lines)

            except Exception as e:
                return f"Error executing query: {str(e)}"

except ImportError:
    # LangChain not installed
    pass
