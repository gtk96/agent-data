"""
真实场景案例：智能客服 Agent
展示框架在实际业务中的应用价值
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
    FunctionStep,
    WorkerAgent,
    AgentOrchestrator,
)
from agent_data.loop.agent_loop import SimpleAgentLoop


async def main():
    print("=" * 60)
    print("案例：智能客服 Agent 系统")
    print("=" * 60)

    # ==================== 1. 初始化数据源 ====================
    print("\n1. 初始化数据源...")

    data_sources = [
        DataSource(
            config=DataSourceConfig(
                name="customers",
                type=DataSourceType.SQL,
                connection=":memory:",
            ),
            description="客户信息表",
            tags=["customer", "user"],
        ),
        DataSource(
            config=DataSourceConfig(
                name="orders",
                type=DataSourceType.SQL,
                connection=":memory:",
            ),
            description="订单表",
            tags=["order", "transaction"],
        ),
        DataSource(
            config=DataSourceConfig(
                name="products",
                type=DataSourceType.SQL,
                connection=":memory:",
            ),
            description="产品表",
            tags=["product", "catalog"],
        ),
    ]

    client = AgentDataClient(data_sources=data_sources)

    # 初始化数据库
    for source in data_sources:
        connector = await client._get_connector(source.name)

    # 客户表
    customers_conn = await client._get_connector("customers")
    customers_conn._connection.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            name TEXT,
            phone TEXT,
            email TEXT,
            vip_level TEXT DEFAULT 'normal'
        )
    """)
    customers_conn._connection.execute("INSERT INTO customers VALUES (1, '张三', '13800138000', 'zhangsan@test.com', 'gold')")
    customers_conn._connection.execute("INSERT INTO customers VALUES (2, '李四', '13900139000', 'lisi@test.com', 'normal')")
    customers_conn._connection.execute("INSERT INTO customers VALUES (3, '王五', '13700137000', 'wangwu@test.com', 'silver')")

    # 订单表
    orders_conn = await client._get_connector("orders")
    orders_conn._connection.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            product_name TEXT,
            amount REAL,
            status TEXT,
            created_at TEXT
        )
    """)
    orders_conn._connection.execute("INSERT INTO orders VALUES (1, 1, 'iPhone 15', 7999.0, 'delivered', '2026-01-15')")
    orders_conn._connection.execute("INSERT INTO orders VALUES (2, 1, 'AirPods Pro', 1899.0, 'delivered', '2026-02-20')")
    orders_conn._connection.execute("INSERT INTO orders VALUES (3, 2, 'MacBook Pro', 14999.0, 'shipping', '2026-03-10')")
    orders_conn._connection.execute("INSERT INTO orders VALUES (4, 3, 'iPad Air', 4799.0, 'pending', '2026-03-15')")

    # 产品表
    products_conn = await client._get_connector("products")
    products_conn._connection.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT,
            category TEXT,
            price REAL,
            stock INTEGER
        )
    """)
    products_conn._connection.execute("INSERT INTO products VALUES (1, 'iPhone 15', '手机', 7999.0, 100)")
    products_conn._connection.execute("INSERT INTO products VALUES (2, 'MacBook Pro', '电脑', 14999.0, 50)")
    products_conn._connection.execute("INSERT INTO products VALUES (3, 'AirPods Pro', '配件', 1899.0, 200)")
    products_conn._connection.execute("INSERT INTO products VALUES (4, 'iPad Air', '平板', 4799.0, 80)")

    print("   ✓ 数据源初始化完成")

    # ==================== 2. 客户查询场景 ====================
    print("\n2. 场景一：客户查询订单")

    context = AgentContext(
        agent_id="customer_service",
        session_id="session_001",
        user_id="1",
    )

    # 查询客户信息
    result = await client.query(
        Query(source="customers", query_type=QueryType.SELECT,
              filters=[{"field": "id", "operator": "eq", "value": 1}]),
        context=context,
    )
    print(f"   客户信息: {result.data[0]['name']} ({result.data[0]['vip_level']})")

    # 查询该客户的订单
    result = await client.query(
        Query(source="orders", query_type=QueryType.SELECT,
              filters=[{"field": "customer_id", "operator": "eq", "value": 1}]),
        context=context,
    )
    print(f"   订单数量: {len(result.data)}")
    for order in result.data:
        print(f"     - {order['product_name']}: ¥{order['amount']} ({order['status']})")

    # ==================== 3. 任务执行场景 ====================
    print("\n3. 场景二：自动化订单处理")

    async def process_order(input_data):
        """订单处理任务"""
        order_id = input_data.get("order_id")

        # 查询订单
        order_result = await client.query(
            Query(source="orders", query_type=QueryType.SELECT,
                  filters=[{"field": "id", "operator": "eq", "value": order_id}]),
        )

        if not order_result.data:
            return {"success": False, "error": "订单不存在"}

        order = order_result.data[0]

        # 查询产品库存
        product_result = await client.query(
            Query(source="products", query_type=QueryType.SELECT,
                  filters=[{"field": "name", "operator": "eq", "value": order["product_name"]}]),
        )

        if product_result.data:
            product = product_result.data[0]
            if product["stock"] > 0:
                return {
                    "success": True,
                    "order_id": order_id,
                    "product": order["product_name"],
                    "amount": order["amount"],
                    "status": "处理中",
                }

        return {"success": False, "error": "库存不足"}

    task = Task(name="process_order", input_data={"order_id": 4})
    result = await client.execute_task(task, process_order)
    print(f"   订单处理结果: {result.output}")

    # ==================== 4. 工作流场景 ====================
    print("\n4. 场景三：VIP 客户服务流程")

    async def check_vip_level(state):
        """检查 VIP 等级"""
        customer_id = state.get("customer_id")
        result = await client.query(
            Query(source="customers", query_type=QueryType.SELECT,
                  filters=[{"field": "id", "operator": "eq", "value": customer_id}]),
        )
        vip_level = result.data[0]["vip_level"] if result.data else "normal"
        return {"vip_level": vip_level, "customer_name": result.data[0]["name"] if result.data else "Unknown"}

    async def apply_discount(state):
        """应用折扣"""
        vip_level = state.get("vip_level", "normal")
        discounts = {"gold": 0.15, "silver": 0.10, "normal": 0.05}
        discount = discounts.get(vip_level, 0.05)
        return {"discount": discount, "discount_text": f"{int(discount * 100)}%"}

    async def generate_response(state):
        """生成回复"""
        name = state.get("customer_name", "客户")
        discount = state.get("discount_text", "5%")
        return {
            "message": f"尊敬的{name}，作为{state.get('vip_level', '普通')}会员，您享受{discount}折扣优惠！"
        }

    workflow = [
        FunctionStep("check_vip", check_vip_level),
        FunctionStep("apply_discount", apply_discount),
        FunctionStep("generate_response", generate_response),
    ]

    result = await client.execute_workflow(
        workflow,
        initial_state={"customer_id": 1},
    )
    print(f"   服务回复: {result['state']['message']}")

    # ==================== 5. Agent Loop 场景 ====================
    print("\n5. 场景四：智能推荐循环")

    iteration = 0

    async def recommendation_step(state):
        """推荐步骤"""
        nonlocal iteration
        iteration += 1

        # 模拟根据用户行为逐步优化推荐
        if iteration == 1:
            state["recommendations"] = ["iPhone 15", "MacBook Pro"]
            state["confidence"] = 0.6
        elif iteration == 2:
            state["recommendations"] = ["iPhone 15", "AirPods Pro"]
            state["confidence"] = 0.8
        else:
            state["recommendations"] = ["iPhone 15"]
            state["confidence"] = 0.95

        state["iteration"] = iteration
        return state

    def is_complete(state):
        return state.get("confidence", 0) >= 0.9

    loop = SimpleAgentLoop(recommendation_step, is_complete)
    result = await client.agent_loop(loop, {"user_id": 1}, max_iterations=10)

    # 获取最终状态
    final_state = result.history[-1]["state_keys"] if result.history else []
    print(f"   推荐结果: 已完成 {result.iterations} 次迭代")
    print(f"   最终状态: {result.status.value}")

    # ==================== 6. 多 Agent 协作场景 ====================
    print("\n6. 场景五：多 Agent 协作处理复杂咨询")

    async def order_agent(input_data):
        """订单 Agent"""
        customer_id = input_data.get("customer_id")
        result = await client.query(
            Query(source="orders", query_type=QueryType.SELECT,
                  filters=[{"field": "customer_id", "operator": "eq", "value": customer_id}]),
        )
        return {"orders": result.data, "order_count": len(result.data)}

    async def product_agent(input_data):
        """产品 Agent"""
        product_names = input_data.get("product_names", [])
        products = []
        for name in product_names:
            result = await client.query(
                Query(source="products", query_type=QueryType.SELECT,
                      filters=[{"field": "name", "operator": "eq", "value": name}]),
            )
            if result.data:
                products.append(result.data[0])
        return {"products": products}

    async def summary_agent(input_data):
        """汇总 Agent"""
        orders = input_data.get("orders", [])
        products = input_data.get("products", [])

        total_amount = sum(o.get("amount", 0) for o in orders)
        product_list = ", ".join([p.get("name", "") for p in products])

        return {
            "summary": f"客户共有{len(orders)}个订单，总金额¥{total_amount:.2f}，购买产品：{product_list}"
        }

    # 创建 Agents
    order_worker = WorkerAgent("order_agent", order_agent, capabilities=["fetch_orders"])
    product_worker = WorkerAgent("product_agent", product_agent, capabilities=["fetch_products"])
    summary_worker = WorkerAgent("summary_agent", summary_agent, capabilities=["summarize"])

    # 创建编排器
    orchestrator = client.create_orchestrator()
    orchestrator.register(order_worker)
    orchestrator.register(product_worker)
    orchestrator.register(summary_worker)

    # 执行协作工作流
    order_result = await orchestrator.execute_task(
        {"customer_id": 1},
        "fetch_orders",
        "coordinator",
    )

    product_names = [o["product_name"] for o in order_result.content["orders"]]
    product_result = await orchestrator.execute_task(
        {"product_names": product_names},
        "fetch_products",
        "coordinator",
    )

    summary_result = await orchestrator.execute_task(
        {"orders": order_result.content["orders"], "products": product_result.content["products"]},
        "summarize",
        "coordinator",
    )

    print(f"   协作结果: {summary_result.content['summary']}")

    # ==================== 总结 ====================
    print("\n" + "=" * 60)
    print("案例演示完成！")
    print("=" * 60)
    print("\n框架价值总结：")
    print("1. 统一数据访问 - 一个客户端访问多种数据源")
    print("2. 任务自动化 - 将业务逻辑封装为可执行任务")
    print("3. 工作流编排 - 多步骤流程自动执行")
    print("4. 智能循环 - Agent 自主迭代优化结果")
    print("5. 多 Agent 协作 - 分工合作处理复杂场景")
    print("\n适用场景：")
    print("- 智能客服系统")
    print("- 电商推荐引擎")
    print("- 自动化数据处理")
    print("- 企业内部 Agent 平台")


if __name__ == "__main__":
    asyncio.run(main())