# Resume Agent — MCP Server

将简历智诊 Agent 封装为标准 MCP (Model Context Protocol) 技能包，供 Claude Code / Cursor / 任意 MCP 客户端调用。

## 可用工具

| 工具 | 功能 | 参数 |
|------|------|------|
| `diagnose_resume` | 上传简历 → 解析 → 诊断 → 返回存疑点 | `file_path`: 简历文件路径 |
| `list_sessions` | 列出所有面试会话 | 无 |
| `get_session_detail` | 获取会话详情（解析结果+诊断报告） | `session_id` |
| `start_interview` | 开始模拟面试，返回第一个问题 | `session_id`, `selected_point_ids`(可选) |
| `answer_interview` | 提交回答，返回下一个问题或报告 | `session_id`, `answer` |
| `skip_question` | 跳过当前存疑点 | `session_id` |
| `end_interview` | 提前结束面试并生成报告 | `session_id` |
| `get_report` | 获取评估报告 | `session_id` |

## 配置方式

### Claude Code

在项目根目录创建 `.claude/settings.json`：

```json
{
  "mcpServers": {
    "resume-agent": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/path/to/resume-agent/backend",
      "env": {
        "LLM_API_KEY": "sk-xxx",
        "LLM_BASE_URL": "https://api.deepseek.com",
        "LLM_MODEL": "deepseek-chat",
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/resume_agent",
        "REDIS_URL": "redis://localhost:6379/0"
      }
    }
  }
}
```

### Cursor

在 `.cursor/mcp.json` 中添加同样的配置。

### Docker 环境

如果后端运行在 Docker 中，MCP server 需要连接 Docker 内的服务：

```json
{
  "mcpServers": {
    "resume-agent": {
      "command": "docker",
      "args": ["exec", "-i", "resume-agent-backend-1", "python", "-m", "app.mcp.server"],
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/resume_agent",
        "REDIS_URL": "redis://localhost:6379/0"
      }
    }
  }
}
```

## 使用示例

### 在 Claude Code 中使用

```
用户：帮我诊断一下这份简历 /Users/me/resume.pdf

Claude：我来调用简历诊断工具。
  → 调用 diagnose_resume(file_path="/Users/me/resume.pdf")
  → 返回诊断结果：3 个存疑点（高优 1 个，中优 2 个）

用户：选前两个存疑点开始面试

Claude：好的，开始面试。
  → 调用 start_interview(session_id="xxx", selected_point_ids=["dp1", "dp2"])
  → 返回第一个问题："你简历中提到日均处理10万+订单，能详细说说吗？"

用户：我用了 Redis 缓存热点数据，MySQL 做持久化...

Claude：收到，让我评估你的回答。
  → 调用 answer_interview(session_id="xxx", answer="...")
  → 返回下一个问题或面试报告
```

### 完整面试流程

```
1. diagnose_resume(file_path="resume.pdf")
   → 返回 session_id + 存疑点列表

2. start_interview(session_id, selected_point_ids=["dp1"])
   → 返回第一个问题

3. answer_interview(session_id, "我的回答...")
   → 返回下一个问题（或 type=complete 含报告）

4. 重复步骤 3 直到所有存疑点处理完

5. get_report(session_id)
   → 返回完整评估报告
```

## 架构

```
MCP Client (Claude Code / Cursor)
    │
    │ MCP Protocol (stdio)
    │
    ▼
MCP Server (app/mcp/server.py)
    │
    │ HTTP API 调用
    │
    ▼
FastAPI Backend (app/api/)
    │
    ├── Celery 异步任务（解析/诊断）
    ├── LangGraph Agent（面试状态机）
    └── PostgreSQL + Redis（持久化）
```

MCP Server 通过 HTTP 调用本地 FastAPI 后端，复用所有已有逻辑，不需要重复实现。
