"""NL2SQL usage example.

This example demonstrates how to use the NL2SQL engine
to query databases using natural language.
"""

import asyncio
import os

from agent_data.core.models import DataSource, DataSourceConfig, DataSourceType
from agent_data.llm import LLMConfig, create_llm
from agent_data.nl2sql import NL2SQLEngine


async def main():
    # 1. Configure LLM
    llm_config = LLMConfig(
        provider="agnes",
        api_url=os.getenv("AGNES_API_URL", "https://api.example.com/v1"),
        api_key=os.getenv("AGNES_API_KEY", "your-api-key"),
        model="agnes-2.0-flash",
        temperature=0.0,
        max_tokens=4096,
    )

    llm = create_llm(llm_config)

    # 2. Configure data source (SQLite for example)
    from agent_data.connectors.sql import SQLConnector

    db_config = DataSourceConfig(
        name="example_db",
        type=DataSourceType.SQL,
        connection=":memory:",  # In-memory SQLite for demo
    )

    connector = SQLConnector(db_config)
    await connector.connect()

    # Create sample table and data
    connector._connection.execute("""
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY,
            product TEXT,
            amount REAL,
            date TEXT
        )
    """)
    connector._connection.execute("""
        INSERT INTO sales (product, amount, date) VALUES
        ('Product A', 100.50, '2024-01-15'),
        ('Product B', 200.00, '2024-01-20'),
        ('Product A', 150.75, '2024-02-10'),
        ('Product C', 300.00, '2024-02-15'),
        ('Product B', 250.50, '2024-03-01')
    """)

    # 3. Create NL2SQL engine
    engine = NL2SQLEngine(
        llm=llm,
        connector=connector,
        config={
            "max_rows": 100,
            "timeout_seconds": 30,
            "enable_memory": True,
        },
    )

    # 4. Query using natural language
    print("=== NL2SQL Demo ===\n")

    # Query 1: Simple query
    result = await engine.query("What products are in the sales table?")
    print(f"Question: {result.question}")
    print(f"SQL: {result.sql}")
    print(f"Answer: {result.answer}")
    print(f"Data: {result.data}")
    print()

    # Query 2: Aggregation
    result = await engine.query("What is the total sales amount?")
    print(f"Question: {result.question}")
    print(f"SQL: {result.sql}")
    print(f"Answer: {result.answer}")
    print()

    # Query 3: Follow-up question (uses conversation memory)
    result = await engine.query("How about for Product A only?")
    print(f"Question: {result.question}")
    print(f"SQL: {result.sql}")
    print(f"Answer: {result.answer}")
    print()

    # 5. Health check
    health = await engine.health_check()
    print(f"Health: {health}")

    # Cleanup
    await connector.close()
    await llm.close()


if __name__ == "__main__":
    asyncio.run(main())
