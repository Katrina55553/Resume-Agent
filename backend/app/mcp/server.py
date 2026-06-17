"""MCP Server — 简历智诊 Agent 技能包（独立运行版）

将简历诊断、模拟面试、评估报告封装为 MCP 标准工具。
直接调用内部模块，无需启动 FastAPI 后端服务。

使用方式：
    python -m app.mcp.server

Claude Code 配置 (.claude/settings.json):
{
  "mcpServers": {
    "resume-agent": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/path/to/backend"
    }
  }
}
"""

import asyncio
import contextlib
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from app.core.database import async_session_maker
from app.models.session import Session, SessionStatus

logger = logging.getLogger(__name__)

server = Server("resume-agent")


def _text(content: str) -> list[TextContent]:
    return [TextContent(type="text", text=content)]


def _json_text(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]


# ============================================================
# 工具定义
# ============================================================


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="diagnose_resume",
            description="上传简历文件，AI 解析 + 诊断，返回结构化数据和存疑点。支持 PDF/Word/TXT。",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "简历文件绝对路径"},
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="start_interview",
            description="开始模拟面试。返回第一个问题。可选指定存疑点 ID 列表。",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "会话 ID"},
                    "selected_point_ids": {
                        "type": "array", "items": {"type": "string"},
                        "description": "可选，要面试的存疑点 ID",
                    },
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="answer_interview",
            description="提交面试回答，返回下一个问题或最终报告。返回值含 type: question/complete。",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "会话 ID"},
                    "answer": {"type": "string", "description": "面试回答"},
                },
                "required": ["session_id", "answer"],
            },
        ),
        Tool(
            name="skip_question",
            description="跳过当前存疑点，切换到下一个。",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "会话 ID"},
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="end_interview",
            description="提前结束面试，根据已有回答生成报告。",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "会话 ID"},
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="get_report",
            description="获取面试评估报告（评分 + 逐点反馈 + 改进建议）。",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "会话 ID"},
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="list_sessions",
            description="列出所有会话及状态。",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


# ============================================================
# 工具实现（直接调用内部模块）
# ============================================================


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "diagnose_resume":
            return await _diagnose_resume(arguments)
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
        elif name == "list_sessions":
            return await _list_sessions()
        else:
            return _text(f"未知工具: {name}")
    except Exception as e:
        logger.error(f"工具 {name} 执行失败: {e}", exc_info=True)
        return _text(f"执行失败: {e}")


async def _diagnose_resume(arguments: dict) -> list[TextContent]:
    """上传简历 → 解析 → 诊断（直接调用 Celery task 同步执行）"""
    import shutil
    import uuid as uuid_lib

    from app.tasks.diagnose_task import diagnose_resume as diagnose_task
    from app.tasks.parse_task import parse_resume

    file_path = arguments["file_path"]
    if not os.path.exists(file_path):
        return _text(f"文件不存在: {file_path}")

    session_id = uuid_lib.uuid4()
    ext = Path(file_path).suffix.lower()
    sub_dir = Path("uploads") / str(session_id)[:2]
    sub_dir.mkdir(parents=True, exist_ok=True)
    dest = sub_dir / f"{session_id}{ext}"
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

    # 同步执行解析和诊断
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, lambda: parse_resume.apply(args=[str(session_id), str(dest)]).get(timeout=120))
        await loop.run_in_executor(None, lambda: diagnose_task.apply(args=[str(session_id)]).get(timeout=120))
    except Exception as e:
        return _text(f"解析/诊断失败: {e}")

    # 读取结果
    async with async_session_maker() as db:
        from sqlalchemy import select
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        parsed = json.loads(session.parsed_content) if session and session.parsed_content else {}

    diag = parsed.get("diagnose_result", {})
    return _json_text({
        "session_id": str(session_id),
        "status": "diagnosed",
        "summary": {
            "name": parsed.get("name"),
            "skills": [s.get("skills", []) for s in parsed.get("skills", [])],
            "work_count": len(parsed.get("work_experience", [])),
            "project_count": len(parsed.get("projects", [])),
        },
        "overall": diag.get("overall", {}),
        "doubt_points": [
            {"id": dp.get("id"), "priority": dp.get("priority"), "reason": dp.get("reason")}
            for dp in diag.get("doubt_points", [])
        ],
    })


async def _load_session(session_id: str):
    """加载 session 和解析结果"""
    from sqlalchemy import select
    async with async_session_maker() as db:
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            return None, None, None
        parsed = json.loads(session.parsed_content) if session.parsed_content else {}
        doubt_points = parsed.get("diagnose_result", {}).get("doubt_points", [])
        return session, parsed, doubt_points


async def _start_interview(arguments: dict) -> list[TextContent]:
    """开始面试"""
    import uuid as uuid_lib

    from app.agent.nodes.question import generate_question
    from app.models.interview import InterviewMessageORM, InterviewStateORM

    session_id = arguments["session_id"]
    selected_ids = arguments.get("selected_point_ids", [])

    session, parsed, doubt_points = await _load_session(session_id)
    if not session:
        return _text(f"会话不存在: {session_id}")
    if session.status not in (SessionStatus.DIAGNOSED, SessionStatus.INTERVIEWING, SessionStatus.COMPLETED):
        return _text(f"请先完成诊断，当前状态: {session.status.value}")

    # 过滤存疑点
    if selected_ids:
        doubt_points = [dp for dp in doubt_points if dp.get("id") in selected_ids]

    if not doubt_points:
        return _text("没有可用的存疑点")

    # 初始化状态
    point_states = {dp.get("id", f"p_{i}"): ("active" if i == 0 else "pending") for i, dp in enumerate(doubt_points)}

    async with async_session_maker() as db:
        # 清除旧面试状态
        from sqlalchemy import delete as sql_delete
        from sqlalchemy import select
        existing = await db.execute(select(InterviewStateORM).where(InterviewStateORM.session_id == session_id))
        old = existing.scalar_one_or_none()
        if old:
            await db.execute(sql_delete(InterviewMessageORM).where(InterviewMessageORM.session_id == session_id))
            await db.delete(old)
            await db.flush()

        # 创建新状态
        state_orm = InterviewStateORM(
            id=uuid_lib.uuid4(), session_id=session_id,
            current_point_index=0, current_round=1,
            point_states=point_states, is_completed=False,
        )
        db.add(state_orm)

        # 生成第一个问题
        state = {
            "doubt_points": doubt_points, "current_point_index": 0,
            "current_round": 1, "point_states": point_states,
            "messages": [], "current_question": None, "current_answer": None,
            "resume_data": {k: v for k, v in parsed.items() if k != "diagnose_result"},
        }
        update = await generate_question(state)
        question_text = update.get("current_question", "")
        point_id = doubt_points[0].get("id", "p_0")

        # 保存消息
        msg = InterviewMessageORM(
            id=uuid_lib.uuid4(), session_id=session_id,
            role="assistant", content=question_text, point_id=point_id,
        )
        db.add(msg)

        # 更新 session 状态
        session.status = SessionStatus.INTERVIEWING
        await db.commit()

    return _json_text({
        "session_id": str(session_id),
        "status": "started",
        "first_question": question_text,
        "point_id": point_id,
        "total_points": len(doubt_points),
    })


async def _load_interview_state(session_id: str) -> dict | None:
    """加载面试状态"""
    from sqlalchemy import select

    from app.models.interview import InterviewMessageORM, InterviewStateORM

    async with async_session_maker() as db:
        result = await db.execute(select(InterviewStateORM).where(InterviewStateORM.session_id == session_id))
        state_orm = result.scalar_one_or_none()
        if not state_orm:
            return None

        msg_result = await db.execute(
            select(InterviewMessageORM).where(InterviewMessageORM.session_id == session_id).order_by(InterviewMessageORM.created_at)
        )
        messages = [{"role": m.role, "content": m.content, "point_id": m.point_id or ""} for m in msg_result.scalars().all()]

        session_result = await db.execute(select(Session).where(Session.id == session_id))
        session = session_result.scalar_one_or_none()
        all_dp = []
        if session and session.parsed_content:
            parsed = json.loads(session.parsed_content)
            all_dp = parsed.get("diagnose_result", {}).get("doubt_points", [])
            resume_data = {k: v for k, v in parsed.items() if k != "diagnose_result"}
        else:
            resume_data = {}

        saved_states = state_orm.point_states or {}
        doubt_points = [dp for dp in all_dp if dp.get("id") in saved_states] if saved_states else all_dp

        return {
            "session_id": str(session_id),
            "doubt_points": doubt_points,
            "current_point_index": state_orm.current_point_index,
            "current_round": state_orm.current_round,
            "point_states": state_orm.point_states or {},
            "messages": messages,
            "is_completed": state_orm.is_completed,
            "evaluations": [],
            "resume_data": resume_data,
            "current_question": None, "current_answer": None,
            "current_evaluation": None, "decision": None,
        }


def _get_point_info(state: dict) -> tuple:
    dp = state.get("doubt_points", [])
    idx = state.get("current_point_index", 0)
    if dp and idx < len(dp):
        return dp[idx].get("id", f"p_{idx}"), idx
    return "", idx


def _compute_progress(state: dict) -> float:
    dp = state.get("doubt_points", [])
    if not dp:
        return 1.0
    ps = state.get("point_states", {})
    done = sum(1 for s in ps.values() if s in ("resolved", "skipped"))
    return round(done / len(dp), 2)


async def _answer_interview(arguments: dict) -> list[TextContent]:
    """提交回答"""
    import uuid as uuid_lib

    from app.agent.nodes.collect import collect_answer
    from app.agent.nodes.evaluate import evaluate_answer
    from app.agent.nodes.question import generate_question
    from app.agent.nodes.report import generate_report
    from app.models.interview import InterviewMessageORM

    session_id = arguments["session_id"]
    answer = arguments["answer"]

    state = await _load_interview_state(session_id)
    if not state:
        return _text("面试未开始")
    if state.get("is_completed"):
        return _text("面试已结束")

    state["current_answer"] = answer
    point_id, _ = _get_point_info(state)

    # collect
    collect_update = await collect_answer(state)
    state["messages"].extend(collect_update.get("messages", []))
    if collect_update.get("answer_too_short"):
        state["answer_too_short"] = True

    # evaluate
    eval_update = await evaluate_answer(state)
    decision = eval_update.get("decision", "follow_up")
    state.update(eval_update)
    if "messages" in eval_update:
        state["messages"] = list(eval_update["messages"])

    evaluations = state.get("evaluations", [])
    cur_eval = state.get("current_evaluation", {})
    if cur_eval:
        cur_eval["point_index"] = state.get("current_point_index", 0)
        evaluations.append(cur_eval)
        state["evaluations"] = evaluations

    # 保存用户消息
    async with async_session_maker() as db:
        msg = InterviewMessageORM(
            id=uuid_lib.uuid4(), session_id=session_id,
            role="user", content=answer, point_id=point_id,
        )
        db.add(msg)
        await db.commit()

    # 按决策分支处理
    if decision == "report":
        report_update = await generate_report(state)
        state.update(report_update)
        await _save_interview_result(session_id, state)
        return _json_text({"type": "complete", "report": state.get("report")})

    # follow_up 或 next_point
    question_update = await generate_question(state)
    state.update(question_update)
    new_point_id, _ = _get_point_info(state)
    question_text = state.get("current_question", "")

    await _save_interview_result(session_id, state, question_text, new_point_id)

    return _json_text({
        "type": "question",
        "question": question_text,
        "point_id": new_point_id,
        "decision": decision,
        "round": state.get("current_round", 1),
        "progress": _compute_progress(state),
    })


async def _save_interview_result(session_id: str, state: dict, question_text: str = None, point_id: str = ""):
    """保存面试状态和消息"""
    import json as json_mod
    import uuid as uuid_lib

    from app.models.interview import InterviewMessageORM, InterviewStateORM

    async with async_session_maker() as db:
        from sqlalchemy import select

        # 保存问题消息
        if question_text:
            msg = InterviewMessageORM(
                id=uuid_lib.uuid4(), session_id=session_id,
                role="assistant", content=question_text, point_id=point_id,
            )
            db.add(msg)

        # 更新 checkpoint
        result = await db.execute(select(InterviewStateORM).where(InterviewStateORM.session_id == session_id))
        state_orm = result.scalar_one_or_none()
        if state_orm:
            state_orm.current_point_index = state.get("current_point_index", 0)
            state_orm.current_round = state.get("current_round", 1)
            state_orm.point_states = state.get("point_states", {})
            state_orm.is_completed = state.get("is_completed", False)
            if state.get("report"):
                state_orm.report_json = json_mod.dumps(state["report"], ensure_ascii=False)

        await db.commit()


async def _skip_question(arguments: dict) -> list[TextContent]:
    """跳过当前存疑点"""
    from app.agent.nodes.question import generate_question
    from app.agent.nodes.report import generate_report

    session_id = arguments["session_id"]
    state = await _load_interview_state(session_id)
    if not state:
        return _text("面试未开始")

    dp = state.get("doubt_points", [])
    idx = state.get("current_point_index", 0)
    ps = dict(state.get("point_states", {}))

    if idx < len(dp):
        ps[dp[idx].get("id", f"p_{idx}")] = "skipped"

    next_idx = idx + 1
    state["point_states"] = ps

    if next_idx >= len(dp):
        state["is_completed"] = True
        report_update = await generate_report(state)
        state.update(report_update)
        await _save_interview_result(session_id, state)
        return _json_text({"type": "complete", "report": state.get("report")})

    next_pid = dp[next_idx].get("id", f"p_{next_idx}")
    ps[next_pid] = "active"
    state["current_point_index"] = next_idx
    state["current_round"] = 1

    question_update = await generate_question(state)
    state.update(question_update)
    question_text = state.get("current_question", "")

    await _save_interview_result(session_id, state, question_text, next_pid)

    return _json_text({
        "type": "question",
        "question": question_text,
        "point_id": next_pid,
        "decision": "next_point",
        "progress": _compute_progress(state),
    })


async def _end_interview(arguments: dict) -> list[TextContent]:
    """提前结束面试"""
    from app.agent.nodes.report import _rule_generate_report

    session_id = arguments["session_id"]
    state = await _load_interview_state(session_id)
    if not state:
        return _text("面试未开始")

    # 标记未处理的存疑点为 skipped
    dp = state.get("doubt_points", [])
    ps = dict(state.get("point_states", {}))
    for i, point in enumerate(dp):
        pid = point.get("id", f"p_{i}")
        if ps.get(pid) not in ("resolved", "skipped"):
            ps[pid] = "skipped"

    state["point_states"] = ps
    state["is_completed"] = True

    # 生成报告
    report = _rule_generate_report(state)
    state["report"] = report

    await _save_interview_result(session_id, state)

    # 更新 session 状态
    from sqlalchemy import select
    async with async_session_maker() as db:
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if session:
            session.status = SessionStatus.COMPLETED
            await db.commit()

    return _json_text({"type": "complete", "report": report})


async def _get_report(arguments: dict) -> list[TextContent]:
    """获取报告"""
    import json as json_mod

    from sqlalchemy import select

    from app.models.interview import InterviewStateORM

    session_id = arguments["session_id"]

    async with async_session_maker() as db:
        result = await db.execute(select(InterviewStateORM).where(InterviewStateORM.session_id == session_id))
        state_orm = result.scalar_one_or_none()

    if not state_orm:
        return _text("面试记录不存在")

    report = {}
    if state_orm.report_json:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            report = json_mod.loads(state_orm.report_json)

    return _json_text({"session_id": session_id, "status": "completed" if state_orm.is_completed else "in_progress", "report": report})


async def _list_sessions() -> list[TextContent]:
    """列出会话"""
    from sqlalchemy import select

    async with async_session_maker() as db:
        result = await db.execute(select(Session).order_by(Session.created_at.desc()).limit(20))
        sessions = result.scalars().all()

    return _json_text({
        "sessions": [
            {"session_id": str(s.id), "status": s.status.value, "filename": s.original_filename}
            for s in sessions
        ]
    })


# ============================================================
# 入口
# ============================================================


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
