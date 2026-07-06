# 贡献指南

感谢你对 Agent Data Framework 的关注！

## 如何贡献

### 1. Fork 仓库

```bash
git clone https://github.com/your-username/agent-data.git
cd agent-data
```

### 2. 创建分支

```bash
git checkout -b feature/your-feature
```

### 3. 安装开发依赖

```bash
pip install -e ".[dev]"
```

### 4. 代码规范

- 使用 black 格式化代码：`black agent_data/ tests/`
- 使用 flake8 检查：`flake8 agent_data/`
- 类型注解：使用 Python Type Hints

### 5. 提交代码

```bash
git add .
git commit -m "feat: 添加新功能"
git push origin feature/your-feature
```

### 6. 创建 Pull Request

在 GitHub 上创建 PR，描述你的改动。

## 开发流程

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定模块
pytest tests/test_planning.py -v

# 运行性能测试
python tests/test_performance.py
```

### 代码格式化

```bash
# 格式化代码
black agent_data/ tests/

# 检查格式
black --check agent_data/ tests/
```

### 类型检查

```bash
mypy agent_data/ --ignore-missing-imports
```

## 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

- `feat:` 新功能
- `fix:` 修复 bug
- `docs:` 文档更新
- `style:` 代码格式（不影响功能）
- `refactor:` 重构
- `test:` 测试相关
- `chore:` 构建/工具相关

示例：
```
feat: 添加 Pinecone 连接器
fix: 修复缓存过期问题
docs: 更新 API 文档
```

## 项目结构

```
agent_data/
├── core/           # 核心客户端和模型
├── connectors/     # 数据源连接器
├── cache/          # 缓存模块
├── tracing/        # 追踪模块
├── planning/       # 任务规划引擎
├── workflow/       # 工作流引擎
├── loop/           # Agent Loop
├── multi_agent/    # 多 Agent 协作
├── mcp/            # MCP 协议
└── integrations/   # 框架集成
```

## 添加新连接器

1. 在 `agent_data/connectors/` 下创建新文件
2. 继承 `BaseConnector` 类
3. 实现必要方法
4. 在 `agent_data/connectors/__init__.py` 中注册
5. 添加测试
6. 更新文档

## 问题反馈

- GitHub Issues: 报告 bug 或提出建议
- GitHub Discussions: 讨论想法和问题

## 许可证

贡献即表示你同意将代码以 MIT 许可证发布。