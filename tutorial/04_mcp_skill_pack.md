# MCP 技能包

## 技术原理

MCP（Model Context Protocol）是 Anthropic 推出的标准协议，让 AI 工具能被任意 MCP 客户端调用。

类比：
- **HTTP** 让网页能被任意浏览器访问
- **MCP** 让 AI 工具能被任意 AI IDE 访问

```
Claude Code / Cursor / Windsurf / Continue / ...
    │
    │ MCP 协议（stdio / SSE）
    │
    ▼
MCP Server（你的工具）
    │
    ▼
具体实现（调用内部模块）
```

## 项目中的 MCP Server

定义了 7 个工具：

| 工具 | 功能 | 参数 |
|------|------|------|
| `diagnose_resume` | 上传简历 → 解析 → 诊断 | `file_path` |
| `start_interview` | 开始面试 | `session_id`, `selected_point_ids` |
| `answer_interview` | 提交回答 | `session_id`, `answer` |
| `skip_question` | 跳过当前存疑点 | `session_id` |
| `end_interview` | 结束面试 | `session_id` |
| `get_report` | 获取评估报告 | `session_id` |
| `list_sessions` | 列出所有会话 | 无 |

## 关键代码

### MCP Server 定义

```python
# mcp/server.py
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("resume-agent")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="diagnose_resume",
            description="上传简历文件，AI 解析 + 诊断",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "简历文件路径"},
                },
                "required": ["file_path"],
            },
        ),
        # ... 其他工具
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "diagnose_resume":
        return await _diagnose_resume(arguments)
    elif name == "start_interview":
        return await _start_interview(arguments)
    # ...
```

### 独立运行（不依赖 FastAPI）

```python
# 直接调用内部模块，不需要 HTTP
async def _diagnose_resume(arguments: dict):
    file_path = arguments["file_path"]

    # 直接调用 Celery task（同步执行）
    parse_resume.apply(args=[session_id, file_path]).get(timeout=120)
    diagnose_task.apply(args=[session_id]).get(timeout=120)

    # 从数据库读取结果
    async with async_session_maker() as db:
        session = await db.get(Session, session_id)
        return json.loads(session.parsed_content)
```

### MCP 客户端配置

```json
// Claude Code: .claude/settings.json
{
  "mcpServers": {
    "resume-agent": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/path/to/backend"
    }
  }
}
```

## 为什么用 MCP 而不是 REST API

| | REST API | MCP |
|--|----------|-----|
| 发现 | 需要读文档才知道有哪些接口 | `list_tools()` 自动发现 |
| 描述 | 需要写 OpenAPI spec | `description` 字段自带 |
| 集成 | 每个客户端要写适配代码 | 标准协议，所有 MCP 客户端通用 |
| 交互 | 手动发 HTTP 请求 | AI 自动决定调用哪个工具 |

## 面试高频问题

### Q1: MCP 和 REST API 的本质区别是什么？

**A:** MCP 是**给 AI 用的协议**，REST API 是**给人用的协议**。

REST API 的消费者是程序员，需要读文档、写代码调用。
MCP 的消费者是 AI Agent，通过 `list_tools()` 自动发现工具，通过 `description` 理解用途，通过 `inputSchema` 知道参数格式。

MCP 让 AI 工具变成"即插即用"的插件。

### Q2: MCP 的传输层是什么？

**A:** 两种模式：
- **stdio**：通过标准输入输出通信，适合本地工具（本项目用的）
- **SSE**：通过 HTTP Server-Sent Events 通信，适合远程服务

stdio 模式最简单：`python -m app.mcp.server`，MCP 客户端启动这个进程，通过 stdin/stdout 通信。

### Q3: MCP Server 怎么做到不依赖 FastAPI？

**A:** MCP Server 直接调用内部模块：

```
MCP Server
    │
    ├── import parse_task → 调用 parse_resume.apply()
    ├── import diagnose_task → 调用 diagnose_resume.apply()
    ├── import question → 调用 generate_question()
    └── import database → 直接读写 PostgreSQL
```

不需要 HTTP 中间层，减少了一次网络跳转。FastAPI 是给前端用的，MCP 是给 AI 用的，两条路径独立。

### Q4: 怎么保证 MCP 工具的安全性？

**A:** 目前项目没有做认证，因为 MCP 是本地 stdio 通信，进程权限等同于当前用户。生产环境可以：
1. 加 API Key 验证
2. 限制文件路径访问范围
3. 加请求频率限制

### Q5: 和 LangChain Tool 有什么区别？

**A:**
- **LangChain Tool**：LangChain 生态内的工具格式，只能被 LangChain Agent 调用
- **MCP Tool**：标准协议，能被任何 MCP 客户端调用（Claude Code、Cursor、自定义 Agent）

MCP 是更通用的标准，不绑定任何框架。LangChain Tool 可以通过适配器转成 MCP Tool。
