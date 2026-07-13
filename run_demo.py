"""Demo application for NL2SQL with SQLite database."""

import asyncio
import sqlite3
import os

from agent_data.core.models import DataSourceConfig, DataSourceType
from agent_data.connectors.sql import SQLConnector
from agent_data.llm.config import LLMConfig
from agent_data.llm.agnes import AgnesLLM
from agent_data.nl2sql.engine import NL2SQLEngine
from agent_data.web.app import create_app


async def create_demo_database():
    """Create a demo SQLite database with sample data."""
    db_path = "./data/demo.db"
    os.makedirs("./data", exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            city TEXT,
            register_date TEXT
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            price REAL,
            stock INTEGER
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            amount REAL,
            order_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """
    )

    # Insert sample data
    users = [
        (1, "张三", "zhangsan@example.com", "北京", "2023-01-15"),
        (2, "李四", "lisi@example.com", "上海", "2023-02-20"),
        (3, "王五", "wangwu@example.com", "广州", "2023-03-10"),
        (4, "赵六", "zhaoliu@example.com", "深圳", "2023-04-05"),
        (5, "钱七", "qianqi@example.com", "杭州", "2023-05-18"),
    ]

    products = [
        (1, "笔记本电脑", "电子产品", 5999.00, 100),
        (2, "无线鼠标", "电子产品", 129.00, 500),
        (3, "机械键盘", "电子产品", 399.00, 300),
        (4, "办公椅", "家具", 899.00, 50),
        (5, "显示器", "电子产品", 1999.00, 80),
    ]

    orders = [
        (1, 1, 1, 1, 5999.00, "2024-01-10"),
        (2, 2, 2, 2, 258.00, "2024-01-15"),
        (3, 1, 3, 1, 399.00, "2024-02-01"),
        (4, 3, 1, 1, 5999.00, "2024-02-15"),
        (5, 2, 5, 1, 1999.00, "2024-03-01"),
        (6, 4, 4, 2, 1798.00, "2024-03-10"),
        (7, 1, 2, 3, 387.00, "2024-03-15"),
        (8, 5, 3, 1, 399.00, "2024-04-01"),
    ]

    cursor.executemany("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?)", users)
    cursor.executemany("INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?, ?)", products)
    cursor.executemany("INSERT OR IGNORE INTO orders VALUES (?, ?, ?, ?, ?, ?)", orders)

    conn.commit()
    conn.close()

    print(f"✓ Demo database created at {db_path}")
    return db_path


async def setup_engine():
    """Setup the NL2SQL engine with real LLM."""
    db_path = await create_demo_database()

    # Database connector
    config = DataSourceConfig(
        name="demo_db",
        type=DataSourceType.SQL,
        connection=db_path,
    )
    connector = SQLConnector(config)
    await connector.connect()
    print("✓ Database connector ready")

    # LLM - 从环境变量读取敏感配置
    llm_config = LLMConfig(
        provider="agnes",
        api_url=os.getenv("AGNES_API_URL", "https://apihub.agnes-ai.com/v1"),
        api_key=os.getenv("AGNES_API_KEY", ""),
        model=os.getenv("AGNES_MODEL", "agnes-2.0-flash"),
        temperature=0.0,
        max_tokens=4096,
        timeout=60,
        max_retries=3,
    )
    if not llm_config.api_key:
        print("⚠️  AGNES_API_KEY not set. NL2SQL features will be disabled.")
        llm = None
    else:
        llm = AgnesLLM(llm_config)
        print("✓ LLM (agnes-2.0-flash) ready")

    # NL2SQL engine
    engine = NL2SQLEngine(
        llm=llm,
        connector=connector,
        config={
            "max_rows": 100,
            "timeout_seconds": 30,
            "enable_memory": True,
            "readonly": True,
        },
    )
    print("✓ NL2SQL engine ready")

    return engine


def main():
    """Main entry point."""
    print("=== 智能问数 Demo 应用 ===\n")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    engine = loop.run_until_complete(setup_engine())

    app = create_app(engine=engine)

    print("\n=== 服务已启动 ===")
    print("前端页面: http://localhost:8000")
    print("API 文档: http://localhost:8000/docs")
    print("\n可用接口:")
    print("  POST /api/v1/query           - 自然语言查询")
    print("  POST /api/v1/sql/execute     - 执行 SQL")
    print("  POST /api/v1/history/save    - 保存历史")
    print("  GET  /api/v1/history/list    - 查询历史")
    print("  GET  /api/v1/health          - 健康检查")
    print("\n按 Ctrl+C 停止服务")

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
