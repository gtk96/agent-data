"""
集成示例 - 展示所有模块的协同工作
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_data import (
    AgentDataClient,
    DataSource,
    DataSourceConfig,
    DataSourceType,
    Query,
    QueryType,
    AgentContext,
    Task,
    TaskPlan,
    FunctionStep,
    WorkerAgent,
    AgentOrchestrator,
)
from agent_data.loop.agent_loop import SimpleAgentLoop


async def main():
    """集成示例主函数"""
    print("=" * 60)
    print("Agent Data Framework - 集成示例")
    print("=" * 60)

    # 创建客户端
    data_sources = [
        DataSource(
            config=DataSourceConfig(
                name="users",
                type=DataSourceType.SQL,
                connection=":memory:",
            ),
            description="用户数据库",
        )
    ]
    client = AgentDataClient(data_sources=data_sources)

    # 初始化数据库
    connector = await client._get_connector("users")
    connector._connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT,
            status TEXT
        )
    """)
    connector._connection.execute("INSERT INTO users (name, email, status) VALUES ('Alice', 'alice@test.com', 'active')")
    connector._connection.execute("INSERT INTO users (name, email, status) VALUES ('Bob', 'bob@test.com', 'inactive')")

    # ==================== 1. 基础查询 ====================
    print("\n1. 基础查询")
    result = await client.query(Query(source="users", query_type=QueryType.SELECT))
    print(f"   查询结果: {len(result.data)} 条记录")

    # ==================== 2. 任务执行 ====================
    print("\n2. 任务执行")

    async def query_task(input_data):
        """查询任务执行器"""
        result = await client.query(Query(source="users", query_type=QueryType.SELECT))
        return {"users": result.data, "count": len(result.data)}

    task = Task(name="query_users", input_data={"action": "list"})
    task_result = await client.execute_task(task, query_task)
    print(f"   任务状态: {task_result.status.value}")
    print(f"   查询到用户: {task_result.output['count']} 个")

    # ==================== 3. 工作流执行 ====================
    print("\n3. 工作流执行")

    async def enrich_data(state):
        """数据丰富步骤"""
        users = state.get("users", [])
        enriched = []
        for user in users:
            user["display_name"] = f"{user['name']} ({user['email']})"
            enriched.append(user)
        return {"enriched_users": enriched}

    async def filter_active(state):
        """过滤活跃用户"""
        users = state.get("enriched_users", [])
        active_users = [u for u in users if u.get("status") == "active"]
        return {"active_users": active_users}

    workflow = [
        FunctionStep("enrich", enrich_data),
        FunctionStep("filter", filter_active),
    ]

    workflow_result = await client.execute_workflow(
        workflow,
        initial_state={"users": result.data},
    )
    print(f"   工作流步骤数: {len(workflow_result['results'])}")
    print(f"   活跃用户: {len(workflow_result['state']['active_users'])} 个")

    # ==================== 4. Agent Loop ====================
    print("\n4. Agent Loop")

    iteration = 0

    async def agent_step(state):
        """Agent 循环步骤"""
        nonlocal iteration
        iteration += 1

        # 模拟逐步处理
        if "processed" not in state:
            state["processed"] = []

        state["processed"].append(f"batch_{iteration}")
        state["iteration"] = iteration

        return state

    def is_complete(state):
        """检查是否完成"""
        return state.get("iteration", 0) >= 3

    loop = SimpleAgentLoop(agent_step, is_complete)
    loop_result = await client.agent_loop(loop, {"data": "initial"}, max_iterations=10)
    print(f"   循环状态: {loop_result.status.value}")
    print(f"   执行次数: {loop_result.iterations}")

    # ==================== 5. 多 Agent 协作 ====================
    print("\n5. 多 Agent 协作")

    async def data_agent(input_data):
        """数据 Agent"""
        result = await client.query(Query(source="users", query_type=QueryType.SELECT))
        return {"data": result.data}

    async def analysis_agent(input_data):
        """分析 Agent"""
        data = input_data.get("data", [])
        stats = {
            "total": len(data),
            "active": len([u for u in data if u.get("status") == "active"]),
        }
        return {"stats": stats}

    # 创建 Agents
    data_worker = WorkerAgent("data_agent", data_agent, capabilities=["fetch_data"])
    analysis_worker = WorkerAgent("analysis_agent", analysis_agent, capabilities=["analyze_data"])

    # 创建编排器
    orchestrator = client.create_orchestrator()
    orchestrator.register(data_worker)
    orchestrator.register(analysis_worker)

    # 执行工作流
    workflow_result = await orchestrator.execute_workflow(
        [
            {"type": "fetch_data", "task": {"action": "fetch"}},
            {"type": "analyze_data", "task": {"action": "analyze"}},
        ],
        sender_id="coordinator",
    )

    print(f"   工作流步骤数: {len(workflow_result)}")
    for i, step_result in enumerate(workflow_result):
        status = "✓" if step_result["success"] else "✗"
        print(f"   步骤 {i+1}: {status}")

    # ==================== 总结 ====================
    print("\n" + "=" * 60)
    print("集成示例完成!")
    print("=" * 60)
    print("\n功能覆盖:")
    print("  ✓ 基础数据查询")
    print("  ✓ 任务执行")
    print("  ✓ 工作流编排")
    print("  ✓ Agent 循环")
    print("  ✓ 多 Agent 协作")


if __name__ == "__main__":
    asyncio.run(main())