"""WebSocket 路由

处理实时面试交互，支持断线重连消息补推。
消息协议：
- answer: 提交回答
- skip: 跳过当前存疑点
- rephrase: 换个问法
- start: 开始/恢复面试（重连时补推缓存消息）
"""

import contextlib
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.agent.nodes.collect import collect_answer
from app.agent.nodes.evaluate import evaluate_answer
from app.agent.nodes.question import generate_question, generate_question_stream
from app.agent.nodes.report import generate_report
from app.core.database import async_session_maker
from app.core.msg_cache import get_pending_messages, push_message
from app.models.interview import InterviewMessageORM, InterviewStateORM
from app.models.session import Session

router = APIRouter()

# 活跃的 WebSocket 连接：session_id -> set of websockets
active_connections: dict[str, set[WebSocket]] = {}


async def _send_json(websocket: WebSocket, data: dict) -> None:
    """发送 JSON 消息，吞掉连接已关闭的异常。"""
    with contextlib.suppress(Exception):
        await websocket.send_json(data)


async def _send_and_cache(
    websocket: WebSocket,
    session_id: str,
    data: dict,
) -> None:
    """发送消息并缓存到 Redis。

    如果 WS 发送失败（连接已断），消息仍在 Redis 中，
    下次重连时会补推。
    """
    msg_type = data.get("type", "unknown")
    # 先写 Redis 缓存（确保不丢）
    await push_message(session_id, msg_type, data)
    # 再发 WebSocket
    await _send_json(websocket, data)


async def _load_state_from_db(session_id: str) -> dict | None:
    """在独立的 DB session 中加载面试状态。

    WebSocket 处理不在 FastAPI 的依赖注入体系内，
    需要手动管理 DB session。
    """
    async with async_session_maker() as db:
        # 加载 InterviewState
        result = await db.execute(
            select(InterviewStateORM).where(
                InterviewStateORM.session_id == session_id
            )
        )
        state_orm = result.scalar_one_or_none()
        if not state_orm:
            return None

        # 加载消息
        msg_result = await db.execute(
            select(InterviewMessageORM)
            .where(InterviewMessageORM.session_id == session_id)
            .order_by(InterviewMessageORM.created_at)
        )
        messages = [
            {
                "role": msg.role,
                "content": msg.content,
                "point_id": msg.point_id or "",
            }
            for msg in msg_result.scalars().all()
        ]

        # 加载存疑点和简历数据
        session_result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session_obj = session_result.scalar_one_or_none()
        doubt_points = []
        resume_data = {}
        if session_obj and session_obj.parsed_content:
            try:
                parsed = json.loads(session_obj.parsed_content)
                doubt_points = parsed.get("diagnose_result", {}).get(
                    "doubt_points", []
                )
                resume_data = {k: v for k, v in parsed.items() if k != "diagnose_result"}
            except (json.JSONDecodeError, TypeError):
                pass

    return {
        "session_id": str(session_id),
        "interview_id": str(state_orm.id),
        "doubt_points": doubt_points,
        "resume_data": resume_data,
        "current_point_index": state_orm.current_point_index,
        "current_round": state_orm.current_round,
        "point_states": state_orm.point_states or {},
        "messages": messages,
        "is_completed": state_orm.is_completed,
        "evaluations": [],
        "current_question": None,
        "current_answer": None,
        "current_evaluation": None,
        "decision": None,
        "force_end": False,
        "should_switch_topic": False,
        "phase": "resume_deep_dive",
        "question_count": len([m for m in messages if m["role"] == "assistant"]),
        "follow_up_count": 0,
        "error_count": 0,
        "total_tokens": 0,
        "resume_text": None,
        "resume_summary": None,
        "report": None,
    }


async def _save_message_to_db(
    session_id, role: str, content: str, point_id: str = "",
) -> None:
    """保存一条消息到数据库。"""
    async with async_session_maker() as db:
        import uuid as uuid_lib

        from app.models.interview import InterviewMessageORM
        msg = InterviewMessageORM(
            id=uuid_lib.uuid4(),
            session_id=session_id,
            role=role,
            content=content,
            point_id=point_id or None,
        )
        db.add(msg)
        await db.commit()


async def _save_state_checkpoint_to_db(
    session_id, state: dict,
) -> None:
    """将面试状态 checkpoint 写入数据库。"""
    async with async_session_maker() as db:
        result = await db.execute(
            select(InterviewStateORM).where(
                InterviewStateORM.session_id == session_id
            )
        )
        state_orm = result.scalar_one_or_none()
        if state_orm:
            state_orm.current_point_index = state.get("current_point_index", 0)
            state_orm.current_round = state.get("current_round", 1)
            state_orm.point_states = state.get("point_states", {})
            state_orm.is_completed = state.get("is_completed", False)
            if state.get("report"):
                state_orm.report_json = json.dumps(
                    state["report"], ensure_ascii=False,
                )
            await db.commit()


def _get_current_point_info(state: dict) -> tuple:
    """获取当前存疑点 (point_id, point_index)。"""
    doubt_points = state.get("doubt_points", [])
    point_index = state.get("current_point_index", 0)
    if doubt_points and point_index < len(doubt_points):
        point = doubt_points[point_index]
        return point.get("id", f"point_{point_index}"), point_index
    return "", point_index


def _compute_progress(state: dict) -> float:
    """计算面试进度。"""
    doubt_points = state.get("doubt_points", [])
    if not doubt_points:
        return 1.0
    point_states = state.get("point_states", {})
    done = sum(
        1 for st in point_states.values()
        if st in ("resolved", "skipped")
    )
    return round(done / len(doubt_points), 2)


async def _handle_interview_action(
    websocket: WebSocket,
    session_id: str,
    action_type: str,
    content: str = "",
) -> None:
    """统一处理面试动作（answer / skip / rephrase / start）。"""

    # 1. 加载状态
    state = await _load_state_from_db(session_id)
    if not state:
        await _send_and_cache(websocket, session_id, {
            "type": "error",
            "error": "面试未开始，请先调用 /interview/start",
        })
        return

    if state.get("is_completed") and action_type != "start":
        await _send_and_cache(websocket, session_id, {
            "type": "error",
            "error": "面试已结束",
        })
        return

    point_id, _ = _get_current_point_info(state)

    # ---- skip ----
    if action_type == "skip":
        doubt_points = state.get("doubt_points", [])
        point_index = state.get("current_point_index", 0)
        point_states = dict(state.get("point_states", {}))

        if point_index < len(doubt_points):
            pid = doubt_points[point_index].get("id", f"point_{point_index}")
            point_states[pid] = "skipped"

        next_index = point_index + 1
        state["point_states"] = point_states

        if next_index >= len(doubt_points):
            # 所有点处理完毕
            state["is_completed"] = True
            report_update = await generate_report(state)
            state.update(report_update)

            await _save_message_to_db(
                session_id, "assistant",
                json.dumps(state.get("report", {}), ensure_ascii=False),
            )
            await _save_state_checkpoint_to_db(session_id, state)

            await _send_and_cache(websocket, session_id, {
                "type": "complete",
                "report": state.get("report"),
            })
            # 发送最终状态
            await _send_and_cache(websocket, session_id, {
                "type": "status",
                "point_states": point_states,
                "progress": 1.0,
            })
            return

        # 切换到下一个
        next_pid = doubt_points[next_index].get("id", f"point_{next_index}")
        point_states[next_pid] = "active"
        state["current_point_index"] = next_index
        state["current_round"] = 1

        question_update = await generate_question(state)
        state.update(question_update)
        new_msgs = question_update.get("messages", [])
        state["messages"].extend(new_msgs)

        question_text = state.get("current_question", "")
        await _save_message_to_db(
            session_id, "assistant", question_text, next_pid,
        )
        await _save_state_checkpoint_to_db(session_id, state)

        await _send_and_cache(websocket, session_id, {
            "type": "question",
            "content": question_text,
            "point_id": next_pid,
            "round": 1,
        })
        await _send_and_cache(websocket, session_id, {
            "type": "status",
            "point_states": point_states,
            "progress": _compute_progress(state),
        })
        return

    # ---- rephrase ----
    if action_type == "rephrase":
        question_update = await generate_question(state)
        state.update(question_update)
        new_msgs = question_update.get("messages", [])
        state["messages"].extend(new_msgs)

        question_text = state.get("current_question", "")
        await _save_message_to_db(
            session_id, "assistant", question_text, point_id,
        )
        await _save_state_checkpoint_to_db(session_id, state)

        await _send_and_cache(websocket, session_id, {
            "type": "question",
            "content": question_text,
            "point_id": point_id,
            "round": state.get("current_round", 1),
        })
        return

    # ---- answer ----
    if action_type == "answer":
        state["current_answer"] = content

        # 收集
        collect_update = await collect_answer(state)
        new_messages = collect_update.get("messages", [])
        state["messages"].extend(new_messages)
        if collect_update.get("answer_too_short"):
            state["answer_too_short"] = True

        await _save_message_to_db(session_id, "user", content, point_id)

        # 评估
        eval_update = await evaluate_answer(state)
        decision = eval_update.get("decision", "follow_up")
        state.update(eval_update)
        if "messages" in eval_update:
            state["messages"] = list(eval_update["messages"])

        # 累积评估
        evaluations = state.get("evaluations", [])
        current_eval = state.get("current_evaluation", {})
        if current_eval:
            current_eval["point_index"] = state.get("current_point_index", 0)
            evaluations.append(current_eval)
            state["evaluations"] = evaluations

        if decision == "report":
            report_update = await generate_report(state)
            state.update(report_update)

            await _save_message_to_db(
                session_id, "assistant",
                json.dumps(state.get("report", {}), ensure_ascii=False),
            )
            await _save_state_checkpoint_to_db(session_id, state)

            await _send_and_cache(websocket, session_id, {
                "type": "complete",
                "report": state.get("report"),
            })
            await _send_and_cache(websocket, session_id, {
                "type": "status",
                "point_states": state.get("point_states", {}),
                "progress": 1.0,
            })
            return

        # follow_up 或 next_point：流式生成问题
        import asyncio
        doubt_points = state.get("doubt_points", [])
        point_index = state.get("current_point_index", 0)
        current_point = doubt_points[point_index] if point_index < len(doubt_points) else {}
        new_point_id = current_point.get("id", "")

        # 先发送 question_start 信号
        await _send_json(websocket, {
            "type": "question_start",
            "point_id": new_point_id,
            "round": state.get("current_round", 1),
        })

        # 用队列实现跨线程流式推送
        chunk_queue: asyncio.Queue[str | None] = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def _stream_to_queue():
            """在后台线程中运行生成器，把 chunk 推入队列"""
            try:
                for chunk in generate_question_stream(
                    current_point, state.get("messages", []),
                    state.get("current_round", 1),
                ):
                    loop.call_soon_threadsafe(chunk_queue.put_nowait, chunk)
            finally:
                loop.call_soon_threadsafe(chunk_queue.put_nowait, None)  # 结束信号

        # 启动后台线程
        import threading
        threading.Thread(target=_stream_to_queue, daemon=True).start()

        # 逐 chunk 推送到客户端
        question_text = ""
        while True:
            chunk = await chunk_queue.get()
            if chunk is None:
                break
            question_text += chunk
            await _send_json(websocket, {
                "type": "chunk",
                "content": chunk,
            })

        # 更新 state
        state["current_question"] = question_text
        state["messages"].append({
            "role": "assistant",
            "content": question_text,
            "point_id": new_point_id,
            "round": state.get("current_round", 1),
        })

        await _save_message_to_db(
            session_id, "assistant", question_text, new_point_id,
        )
        await _save_state_checkpoint_to_db(session_id, state)

        # 发送完整问题（用于缓存和最终确认）
        await _send_and_cache(websocket, session_id, {
            "type": "question",
            "content": question_text,
            "point_id": new_point_id,
            "round": state.get("current_round", 1),
        })
        await _send_and_cache(websocket, session_id, {
            "type": "status",
            "point_states": state.get("point_states", {}),
            "progress": _compute_progress(state),
        })
        return

    # ---- start (开始/恢复面试，重连时补推缓存消息) ----
    if action_type == "start":
        # 先检查 Redis 中是否有未消费的缓存消息
        pending = await get_pending_messages(session_id)
        if pending:
            for msg in pending:
                await _send_json(websocket, msg)
            return

        # 无缓存消息，发送当前状态
        if not state.get("is_completed"):
            question_update = await generate_question(state)
            question_text = question_update.get("current_question", "")
            point_id_val, _ = _get_current_point_info(state)

            await _send_and_cache(websocket, session_id, {
                "type": "question",
                "content": question_text,
                "point_id": point_id_val,
                "round": state.get("current_round", 1),
            })
            await _send_and_cache(websocket, session_id, {
                "type": "status",
                "point_states": state.get("point_states", {}),
                "progress": _compute_progress(state),
            })
        return


@router.websocket("/ws/interview/{session_id}")
async def websocket_interview(websocket: WebSocket, session_id: str):
    """面试 WebSocket 连接

    消息协议：
    客户端发送：
        {"type": "answer", "content": "..."}
        {"type": "skip"}
        {"type": "rephrase"}
        {"type": "start"}
    服务端发送：
        {"type": "question", "content": "...", "point_id": "...", "round": N}
        {"type": "status", "point_states": {...}, "progress": 0.5}
        {"type": "complete", "report": {...}}
        {"type": "error", "error": "..."}

    Args:
        websocket: WebSocket 连接
        session_id: 会话 ID
    """
    await websocket.accept()

    # 注册连接
    if session_id not in active_connections:
        active_connections[session_id] = set()
    active_connections[session_id].add(websocket)

    try:
        while True:
            raw = await websocket.receive_text()

            # 解析消息
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _send_and_cache(websocket, session_id, {
                    "type": "error",
                    "error": "无效的 JSON 格式",
                })
                continue

            msg_type = data.get("type", "")
            content = data.get("content", "")

            if msg_type not in ("answer", "skip", "rephrase", "start"):
                await _send_and_cache(websocket, session_id, {
                    "type": "error",
                    "error": f"未知的消息类型: {msg_type}",
                })
                continue

            # answer 必须有内容
            if msg_type == "answer" and not content:
                await _send_and_cache(websocket, session_id, {
                    "type": "error",
                    "error": "回答内容不能为空",
                })
                continue

            # 处理面试动作
            await _handle_interview_action(
                websocket, session_id, msg_type, content,
            )

    except WebSocketDisconnect:
        # 清理连接
        active_connections[session_id].discard(websocket)
        if not active_connections[session_id]:
            del active_connections[session_id]
