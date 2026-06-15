"""MCP Server — 简历智诊 Agent 技能包

将简历诊断、模拟面试、评估报告封装为 MCP 标准工具，
供 Claude Code / Cursor / 任意 MCP 客户端调用。

使用方式：
    # 作为 stdio MCP server
    python -m app.mcp.server

    # Claude Code 配置 (.claude/settings.json):
    # {
    #   "mcpServers": {
    #     "resume-agent": {
    #       "command": "python",
    #       "args": ["-m", "app.mcp.server"],
    #       "cwd": "/path/to/backend"
    #     }
    #   }
    # }
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# 添加 backend 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from app.core.config import settings
from app.core.database import async_session_maker
from app.models.session import Session, SessionStatus

logger = logging.getLogger(__name__)

# ============================================================
# MCP Server 定义
# ============================================================

server = Server("resume-agent")


def _text(content: str) -> list[TextContent]:
    """创建文本内容"""
    return [TextContent(type="text", text=content)]


def _json_text(data: dict) -> list[TextContent]:
    """创建 JSON 文本内容"""
    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]


# ============================================================
# Tool 定义
# ============================================================


@server.list_tools()
async def list_tools() -> list[Tool]:
    """列出所有可用工具"""
    return [
        Tool(
            name="diagnose_resume",
            description=(
                "上传简历文件并获取 AI 诊断报告。"
                "支持 PDF/Word/TXT 格式。"
                "返回结构化解析结果 + 存疑点列表 + 改进建议。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "简历文件的绝对路径",
                    },
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="list_sessions",
            description="列出所有面试会话及其状态",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_session_detail",
            description="获取指定会话的详细信息（解析结果、诊断报告）",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "会话 ID",
                    },
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="start_interview",
            description=(
                "开始模拟面试。返回第一个面试问题。"
                "需要先完成简历诊断（diagnose_resume）。"
                "可选指定要面试的存疑点 ID 列表。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "会话 ID",
                    },
                    "selected_point_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可选，要面试的存疑点 ID 列表。不填则面试所有存疑点。",
                    },
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="answer_interview",
            description=(
                "提交面试回答，获取下一个问题或面试报告。"
                "返回值包含 type 字段：'question'=下一个问题, 'complete'=面试结束（含报告）"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "会话 ID",
                    },
                    "answer": {
                        "type": "string",
                        "description": "你的面试回答",
                    },
                },
                "required": ["session_id", "answer"],
            },
        ),
        Tool(
            name="skip_question",
            description="跳过当前存疑点的面试问题，切换到下一个存疑点",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "会话 ID",
                    },
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="end_interview",
            description="提前结束面试，根据已有回答生成评估报告",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "会话 ID",
                    },
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="get_report",
            description="获取面试评估报告（可信度评分 + 逐点反馈 + 改进建议）",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "会话 ID",
                    },
                },
                "required": ["session_id"],
            },
        ),
    ]


# ============================================================
# Tool 实现
# ============================================================


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """处理工具调用"""

    if name == "diagnose_resume":
        return await _diagnose_resume(arguments)
    elif name == "list_sessions":
        return await _list_sessions()
    elif name == "get_session_detail":
        return await _get_session_detail(arguments)
    elif name == "start_interview":
        return await _start_interview(arguments)
    elif name == "answer_interview":
        return await _answer_interview(arguments)
    elif name == "skip_question":
        return await _skip_question(arguments)
    elif name == "end_interview":
        return await _end_interview(arguments)
    elif name == "get_report":
        return await _get_report(arguments)
    else:
        return _text(f"未知工具: {name}")


# ---------- 诊断简历 ----------

async def _diagnose_resume(arguments: dict) -> list[TextContent]:
    """上传简历并获取诊断报告"""
    file_path = arguments.get("file_path", "")
    if not os.path.exists(file_path):
        return _text(f"文件不存在: {file_path}")

    # 1. 上传文件，创建会话
    import uuid as uuid_lib
    from app.utils.security.file_upload import validate_upload_file_fast
    from app.tasks.parse_task import parse_resume
    from app.tasks.diagnose_task import diagnose_resume

    session_id = uuid_lib.uuid4()
    ext = Path(file_path).suffix.lower()
    sub_dir = Path("uploads") / str(session_id)[:2]
    sub_dir.mkdir(parents=True, exist_ok=True)
    dest = sub_dir / f"{session_id}{ext}"

    # 复制文件
    import shutil
    shutil.copy2(file_path, dest)

    # 创建 DB 记录
    async with async_session_maker() as db:
        session = Session(
            id=session_id,
            status=SessionStatus.UPLOADED,
            original_filename=Path(file_path).name,
            file_path=str(dest),
            file_size=f"{os.path.getsize(file_path) / 1024:.1f}KB",
            mime_type="application/octet-stream",
            progress=0.0,
        )
        db.add(session)
        await db.commit()

    # 2. 同步执行解析和诊断（MCP 调用是同步的）
    # 在线程池中运行 Celery 任务
    loop = asyncio.get_event_loop()

    def _run_parse():
        task = parse_resume.apply(args=[str(session_id), str(dest)])
        return task.get(timeout=120)

    def _run_diagnose():
        task = diagnose_resume.apply(args=[str(session_id)])
        return task.get(timeout=120)

    try:
        await loop.run_in_executor(None, _run_parse)
        await loop.run_in_executor(None, _run_diagnose)
    except Exception as e:
        return _text(f"解析/诊断失败: {e}")

    # 3. 读取结果
    async with async_session_maker() as db:
        from sqlalchemy import select
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            return _text("会话不存在")

        parsed = json.loads(session.parsed_content) if session.parsed_content else {}

    diagnose_result = parsed.get("diagnose_result", {})

    return _json_text({
        "session_id": str(session_id),
        "status": "diagnosed",
        "parsed_data": {
            "name": parsed.get("name"),
            "phone": parsed.get("phone"),
            "email": parsed.get("email"),
            "skills": parsed.get("skills", []),
            "work_experience_count": len(parsed.get("work_experience", [])),
            "education_count": len(parsed.get("education", [])),
            "projects_count": len(parsed.get("projects", [])),
        },
        "diagnose_result": diagnose_result,
    })


# ---------- 列出会话 ----------

async def _list_sessions() -> list[TextContent]:
    """列出所有会话"""
    async with async_session_maker() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(Session).order_by(Session.created_at.desc()).limit(20)
        )
        sessions = result.scalars().all()

    data = []
    for s in sessions:
        data.append({
            "session_id": str(s.id),
            "status": s.status.value if s.status else "unknown",
            "filename": s.original_filename,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })

    return _json_text({"sessions": data})


# ---------- 会话详情 ----------

async def _get_session_detail(arguments: dict) -> list[TextContent]:
    """获取会话详情"""
    session_id = arguments.get("session_id", "")

    async with async_session_maker() as db:
        from sqlalchemy import select
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()

    if not session:
        return _text(f"会话不存在: {session_id}")

    parsed = json.loads(session.parsed_content) if session.parsed_content else {}

    return _json_text({
        "session_id": str(session.id),
        "status": session.status.value if session.status else "unknown",
        "filename": session.original_filename,
        "parsed_data": parsed,
    })


# ---------- 开始面试 ----------

async def _start_interview(arguments: dict) -> list[TextContent]:
    """开始面试"""
    session_id = arguments.get("session_id", "")
    selected_ids = arguments.get("selected_point_ids", [])

    async with async_session_maker() as db:
        from sqlalchemy import select
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()

    if not session:
        return _text(f"会话不存在: {session_id}")

    if session.status not in (SessionStatus.DIAGNOSED, SessionStatus.INTERVIEWING, SessionStatus.COMPLETED):
        return _text(f"请先完成诊断，当前状态: {session.status.value}")

    # 调用 REST API
    import httpx
    base_url = f"http://localhost:8000/api"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base_url}/sessions/{session_id}/interview/start",
            json={"selected_point_ids": selected_ids},
            timeout=30,
        )
        if resp.status_code != 200:
            return _text(f"启动面试失败: {resp.text}")
        data = resp.json()

    return _json_text(data.get("data", data))


# ---------- 提交回答 ----------

async def _answer_interview(arguments: dict) -> list[TextContent]:
    """提交面试回答"""
    session_id = arguments.get("session_id", "")
    answer = arguments.get("answer", "")

    import httpx
    base_url = f"http://localhost:8000/api"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base_url}/sessions/{session_id}/interview/respond",
            json={"content": answer},
            timeout=60,
        )
        if resp.status_code != 200:
            return _text(f"提交回答失败: {resp.text}")
        data = resp.json()

    return _json_text(data.get("data", data))


# ---------- 跳过 ----------

async def _skip_question(arguments: dict) -> list[TextContent]:
    """跳过当前问题"""
    session_id = arguments.get("session_id", "")

    import httpx
    base_url = f"http://localhost:8000/api"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base_url}/sessions/{session_id}/interview/skip",
            timeout=30,
        )
        if resp.status_code != 200:
            return _text(f"跳过失败: {resp.text}")
        data = resp.json()

    return _json_text(data.get("data", data))


# ---------- 结束面试 ----------

async def _end_interview(arguments: dict) -> list[TextContent]:
    """结束面试"""
    session_id = arguments.get("session_id", "")

    import httpx
    base_url = f"http://localhost:8000/api"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base_url}/sessions/{session_id}/interview/end",
            timeout=120,
        )
        if resp.status_code != 200:
            return _text(f"结束面试失败: {resp.text}")
        data = resp.json()

    return _json_text(data.get("data", data))


# ---------- 获取报告 ----------

async def _get_report(arguments: dict) -> list[TextContent]:
    """获取评估报告"""
    session_id = arguments.get("session_id", "")

    import httpx
    base_url = f"http://localhost:8000/api"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{base_url}/sessions/{session_id}/report",
            timeout=30,
        )
        if resp.status_code != 200:
            return _text(f"获取报告失败: {resp.text}")
        data = resp.json()

    return _json_text(data.get("data", data))


# ============================================================
# 入口
# ============================================================


async def main():
    """MCP Server 入口（stdio 模式）"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
