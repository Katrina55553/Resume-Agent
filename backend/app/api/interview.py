"""面试路由

实现面试生命周期管理：开始、回答、跳过、换问法、恢复。
所有端点操作数据库，遵循 InterviewRules 约束。
"""

import json
import uuid as uuid_lib
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.session import Session, SessionStatus
from app.models.interview import (
    InterviewStateORM,
    InterviewMessageORM,
    InterviewStartResponse,
    InterviewRespondRequest,
    InterviewRespondResponse,
    InterviewResumeResponse,
)
from app.agent.nodes.question import generate_question
from app.agent.nodes.collect import collect_answer
from app.agent.nodes.evaluate import evaluate_answer
from app.agent.nodes.report import generate_report

router = APIRouter()


# ============================================================
# 辅助函数
# ============================================================


def _extract_doubt_points(session: Session) -> List[dict]:
    """从 session 的 parsed_content 中提取存疑点列表。

    存疑点存储路径：parsed_content -> diagnose_result -> doubt_points
    """
    if not session.parsed_content:
        return []
    try:
        parsed = json.loads(session.parsed_content)
    except (json.JSONDecodeError, TypeError):
        return []
    diagnose_result = parsed.get("diagnose_result", {})
    return diagnose_result.get("doubt_points", [])


def _build_point_states(doubt_points: List[dict]) -> Dict[str, str]:
    """初始化各存疑点的状态。

    第一个点标记为 active，其余为 pending。
    """
    states = {}
    for i, point in enumerate(doubt_points):
        pid = point.get("id", f"point_{i}")
        states[pid] = "active" if i == 0 else "pending"
    return states


def _build_point_state_list(
    doubt_points: List[dict],
    point_states: Dict[str, str],
) -> List[dict]:
    """将存疑点 + 状态字典合并为前端需要的完整列表。

    返回 [{id, source_text, priority, status}, ...]
    """
    result = []
    for i, point in enumerate(doubt_points):
        pid = point.get("id", f"point_{i}")
        result.append({
            "id": pid,
            "source_text": point.get("source_text", ""),
            "priority": point.get("priority", "low"),
            "status": point_states.get(pid, "pending"),
        })
    return result


async def _load_interview_state(
    db: AsyncSession,
    session_id: str,
) -> Optional[dict]:
    """从数据库加载面试状态，还原为 node 函数可用的 state dict。

    Returns:
        state dict，如果面试未开始则返回 None。
    """
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

    # 加载存疑点和简历数据（从 session）
    session_result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = session_result.scalar_one_or_none()
    doubt_points = _extract_doubt_points(session) if session else []

    # 加载简历结构化数据（供 Tool Calling 使用）
    resume_data = {}
    if session and session.parsed_content:
        try:
            parsed = json.loads(session.parsed_content)
            resume_data = {k: v for k, v in parsed.items() if k != "diagnose_result"}
        except (json.JSONDecodeError, TypeError):
            pass

    # 从 ORM 恢复评估历史（从消息中提取，简化处理）
    evaluations = []
    for msg in messages:
        if msg.get("role") == "user":
            # 为每个用户回答生成一个简单的评估记录
            # 实际评估结果在 evaluate 节点中生成，这里做简化恢复
            evaluations.append({
                "score": 60,  # 恢复时用默认值
                "feedback": "",
                "point_index": 0,
            })

    return {
        "session_id": str(session_id),
        "interview_id": str(state_orm.id),
        "doubt_points": doubt_points,
        "current_point_index": state_orm.current_point_index,
        "current_round": state_orm.current_round,
        "point_states": state_orm.point_states or {},
        "messages": messages,
        "is_completed": state_orm.is_completed,
        "evaluations": evaluations,
        "resume_data": resume_data,
        # 以下字段供节点函数使用
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


async def _save_message(
    db: AsyncSession,
    session_id,
    role: str,
    content: str,
    point_id: str = "",
) -> None:
    """将一条消息保存到 interview_messages 表。"""
    msg = InterviewMessageORM(
        id=uuid_lib.uuid4(),
        session_id=session_id,
        role=role,
        content=content,
        point_id=point_id or None,
    )
    db.add(msg)


async def _save_state_checkpoint(
    db: AsyncSession,
    state_orm: InterviewStateORM,
    state: dict,
) -> None:
    """将当前 state 写回 ORM 对象（checkpoint）。"""
    state_orm.current_point_index = state.get("current_point_index", 0)
    state_orm.current_round = state.get("current_round", 1)
    state_orm.point_states = state.get("point_states", {})
    state_orm.is_completed = state.get("is_completed", False)
    if state.get("report"):
        state_orm.report_json = json.dumps(
            state["report"], ensure_ascii=False,
        )
    await db.flush()


def _get_current_point_info(state: dict) -> tuple:
    """获取当前存疑点的 ID 和索引。

    Returns:
        (point_id, point_index) 元组。
    """
    doubt_points = state.get("doubt_points", [])
    point_index = state.get("current_point_index", 0)
    if doubt_points and point_index < len(doubt_points):
        point = doubt_points[point_index]
        return point.get("id", f"point_{point_index}"), point_index
    return "", point_index


def _compute_progress(state: dict) -> float:
    """计算面试进度（0.0 ~ 1.0）。"""
    doubt_points = state.get("doubt_points", [])
    if not doubt_points:
        return 1.0
    point_states = state.get("point_states", {})
    done = sum(
        1 for pid, st in point_states.items()
        if st in ("resolved", "skipped")
    )
    return round(done / len(doubt_points), 2)


# ============================================================
# 端点实现
# ============================================================


@router.post(
    "/sessions/{session_id}/interview/start",
    response_model=InterviewStartResponse,
)
async def start_interview(
    session_id: str,
    body: Dict[str, Any] = None,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """开始面试

    校验会话状态 → 创建 InterviewState → 生成第一个问题 → 保存消息。
    body.selected_point_ids: 可选，用户选中的存疑点 ID 列表。
    """
    # 1. 查找 session
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail={
            "code": 1002,
            "message": "会话不存在",
        })

    # 2. 校验状态：必须已完成诊断（COMPLETED 也允许，支持重新面试）
    if session.status not in (
        SessionStatus.DIAGNOSED,
        SessionStatus.INTERVIEWING,
        SessionStatus.COMPLETED,
    ):
        raise HTTPException(status_code=400, detail={
            "code": 1003,
            "message": f"请先完成简历诊断，当前状态: {session.status.value}",
        })

    # 3. 提取存疑点
    doubt_points = _extract_doubt_points(session)
    if not doubt_points:
        raise HTTPException(status_code=400, detail={
            "code": 1004,
            "message": "没有存疑点，无法开始面试",
        })

    # 过滤：只保留用户选中的存疑点
    selected_ids = (body or {}).get("selected_point_ids", [])
    if selected_ids:
        doubt_points = [dp for dp in doubt_points if dp.get("id") in selected_ids]
        if not doubt_points:
            raise HTTPException(status_code=400, detail={
                "code": 1004,
                "message": "选中的存疑点无效",
            })

    # 4. 检查是否已有面试状态（幂等）
    existing = await db.execute(
        select(InterviewStateORM).where(
            InterviewStateORM.session_id == session_id
        )
    )
    state_orm = existing.scalar_one_or_none()

    # 面试已完成 → 清除旧状态，允许重新开始
    if state_orm and state_orm.is_completed:
        # 删除旧的面试消息
        from sqlalchemy import delete as sql_delete
        await db.execute(
            sql_delete(InterviewMessageORM).where(
                InterviewMessageORM.session_id == session_id
            )
        )
        # 删除旧的面试状态
        await db.delete(state_orm)
        await db.flush()
        state_orm = None

    if state_orm:
        # 已有状态但未完成，恢复面试
        state = await _load_interview_state(db, session_id)
        return InterviewStartResponse(
            session_id=str(session_id),
            interview_id=str(state_orm.id),
            status="resumed",
            first_question=state.get("current_question", ""),
            point_id=_get_current_point_info(state)[0],
            total_points=len(doubt_points),
            round=state.get("current_round", 1),
        )

    # 5. 创建面试状态
    point_states = _build_point_states(doubt_points)
    state_orm = InterviewStateORM(
        id=uuid_lib.uuid4(),
        session_id=session_id,
        current_point_index=0,
        current_round=1,
        point_states=point_states,
        is_completed=False,
    )
    db.add(state_orm)

    # 6. 构造初始 state，调用问题生成节点
    # 加载简历数据供 Tool Calling 使用
    resume_data = {}
    if session.parsed_content:
        try:
            parsed = json.loads(session.parsed_content)
            resume_data = {k: v for k, v in parsed.items() if k != "diagnose_result"}
        except (json.JSONDecodeError, TypeError):
            pass

    initial_state = {
        "doubt_points": doubt_points,
        "current_point_index": 0,
        "current_round": 1,
        "point_states": point_states,
        "messages": [],
        "current_question": None,
        "current_answer": None,
        "resume_data": resume_data,
    }
    update = await generate_question(initial_state)

    question_text = update.get("current_question", "")
    point_id = doubt_points[0].get("id", "point_0") if doubt_points else ""

    # 7. 保存第一条 AI 消息
    await _save_message(
        db, session_id, "assistant", question_text, point_id,
    )

    # 8. 更新 session 状态
    session.status = SessionStatus.INTERVIEWING
    await db.flush()

    return InterviewStartResponse(
        session_id=str(session_id),
        interview_id=str(state_orm.id),
        status="started",
        first_question=question_text,
        point_id=point_id,
        round=1,
        total_points=len(doubt_points),
        point_list=_build_point_state_list(doubt_points, point_states),
    )


@router.post(
    "/sessions/{session_id}/interview/respond",
    response_model=InterviewRespondResponse,
)
async def respond_interview(
    session_id: str,
    body: InterviewRespondRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """提交回答

    流程：保存回答 → collect → evaluate → 根据决策生成下一问题 / 生成报告。
    """
    # 1. 加载状态
    state = await _load_interview_state(db, session_id)
    if not state:
        raise HTTPException(status_code=404, detail={
            "code": 1002,
            "message": "面试未开始，请先调用 /interview/start",
        })
    if state.get("is_completed"):
        raise HTTPException(status_code=400, detail={
            "code": 1005,
            "message": "面试已结束",
        })

    # 2. 设置用户回答
    state["current_answer"] = body.content

    # 3. 收集回答
    collect_update = await collect_answer(state)
    # 合并 collect 结果（messages 使用 add reducer，手动 append）
    new_messages = collect_update.get("messages", [])
    state["messages"].extend(new_messages)
    if collect_update.get("answer_too_short"):
        state["answer_too_short"] = True

    # 4. 保存用户消息到 DB
    point_id, _ = _get_current_point_info(state)
    await _save_message(db, session_id, "user", body.content, point_id)

    # 5. 评估回答
    eval_update = await evaluate_answer(state)
    decision = eval_update.get("decision", "follow_up")
    state.update(eval_update)
    # 保护 messages 不被覆盖
    if "messages" in eval_update:
        state["messages"] = list(eval_update["messages"])

    # 6. 累积评估历史
    evaluations = state.get("evaluations", [])
    current_eval = state.get("current_evaluation", {})
    if current_eval:
        current_eval["point_index"] = state.get("current_point_index", 0)
        evaluations.append(current_eval)
        state["evaluations"] = evaluations

    # 7. 获取 ORM 对象用于 checkpoint
    orm_result = await db.execute(
        select(InterviewStateORM).where(
            InterviewStateORM.session_id == session_id
        )
    )
    state_orm = orm_result.scalar_one_or_none()

    # 根据决策分支处理
    if decision == "report":
        # 所有存疑点处理完毕，生成报告
        report_update = await generate_report(state)
        state.update(report_update)

        # 保存报告消息
        report_json = json.dumps(
            state.get("report", {}), ensure_ascii=False,
        )
        await _save_message(
            db, session_id, "assistant",
            f"[面试报告]\n{report_json}", "",
        )

        # checkpoint
        if state_orm:
            await _save_state_checkpoint(db, state_orm, state)

        return InterviewRespondResponse(
            session_id=str(session_id),
            decision="report",
            point_states=state.get("point_states", {}),
            progress=1.0,
            report=state.get("report"),
        )

    elif decision == "next_point":
        # 切换到下一个存疑点，生成新问题
        question_update = await generate_question(state)
        state.update(question_update)
        new_msgs = question_update.get("messages", [])
        state["messages"].extend(new_msgs)

        new_point_id, _ = _get_current_point_info(state)
        question_text = state.get("current_question", "")

        await _save_message(
            db, session_id, "assistant", question_text, new_point_id,
        )

        if state_orm:
            await _save_state_checkpoint(db, state_orm, state)

        return InterviewRespondResponse(
            session_id=str(session_id),
            decision="next_point",
            question=question_text,
            point_id=new_point_id,
            round=state.get("current_round", 1),
            point_states=state.get("point_states", {}),
            progress=_compute_progress(state),
        )

    else:
        # follow_up：继续追问
        question_update = await generate_question(state)
        state.update(question_update)
        new_msgs = question_update.get("messages", [])
        state["messages"].extend(new_msgs)

        question_text = state.get("current_question", "")

        await _save_message(
            db, session_id, "assistant", question_text, point_id,
        )

        if state_orm:
            await _save_state_checkpoint(db, state_orm, state)

        return InterviewRespondResponse(
            session_id=str(session_id),
            decision="follow_up",
            question=question_text,
            point_id=point_id,
            round=state.get("current_round", 1),
            point_states=state.get("point_states", {}),
            progress=_compute_progress(state),
        )


@router.post("/sessions/{session_id}/interview/skip")
async def skip_current_point(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """跳过当前存疑点

    将当前存疑点标记为 skipped，切换到下一个，生成新问题。
    """
    state = await _load_interview_state(db, session_id)
    if not state:
        raise HTTPException(status_code=404, detail={
            "code": 1002,
            "message": "面试未开始",
        })
    if state.get("is_completed"):
        raise HTTPException(status_code=400, detail={
            "code": 1005,
            "message": "面试已结束",
        })

    doubt_points = state.get("doubt_points", [])
    point_index = state.get("current_point_index", 0)
    point_states = dict(state.get("point_states", {}))

    # 标记当前点为 skipped
    if point_index < len(doubt_points):
        current_pid = doubt_points[point_index].get("id", f"point_{point_index}")
        point_states[current_pid] = "skipped"

    # 切换到下一个
    next_index = point_index + 1

    # 获取 ORM 对象
    orm_result = await db.execute(
        select(InterviewStateORM).where(
            InterviewStateORM.session_id == session_id
        )
    )
    state_orm = orm_result.scalar_one_or_none()

    # 所有点都处理完了
    if next_index >= len(doubt_points):
        state["point_states"] = point_states
        state["current_point_index"] = next_index
        state["is_completed"] = True

        # 生成报告
        report_update = await generate_report(state)
        state.update(report_update)

        report_json = json.dumps(
            state.get("report", {}), ensure_ascii=False,
        )
        await _save_message(
            db, session_id, "assistant",
            f"[面试报告]\n{report_json}", "",
        )

        if state_orm:
            await _save_state_checkpoint(db, state_orm, state)

        return {
            "code": 0,
            "message": "存疑点已跳过，所有存疑点处理完毕",
            "data": {
                "session_id": str(session_id),
                "decision": "report",
                "point_states": point_states,
                "progress": 1.0,
                "report": state.get("report"),
            },
        }

    # 切换到下一个存疑点
    next_pid = doubt_points[next_index].get("id", f"point_{next_index}")
    point_states[next_pid] = "active"

    state["point_states"] = point_states
    state["current_point_index"] = next_index
    state["current_round"] = 1

    # 生成新问题
    question_update = await generate_question(state)
    state.update(question_update)
    new_msgs = question_update.get("messages", [])
    state["messages"].extend(new_msgs)

    question_text = state.get("current_question", "")

    await _save_message(
        db, session_id, "assistant", question_text, next_pid,
    )

    if state_orm:
        await _save_state_checkpoint(db, state_orm, state)

    return {
        "code": 0,
        "message": "已跳过当前存疑点",
        "data": {
            "session_id": str(session_id),
            "decision": "next_point",
            "question": question_text,
            "point_id": next_pid,
            "round": 1,
            "point_states": point_states,
            "progress": _compute_progress(state),
        },
    }


@router.post("/sessions/{session_id}/interview/rephrase")
async def rephrase_question(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """换个问法

    重新生成当前存疑点的问题（不增加轮次）。
    """
    state = await _load_interview_state(db, session_id)
    if not state:
        raise HTTPException(status_code=404, detail={
            "code": 1002,
            "message": "面试未开始",
        })
    if state.get("is_completed"):
        raise HTTPException(status_code=400, detail={
            "code": 1005,
            "message": "面试已结束",
        })

    # 生成新问题（mock 实现中同一轮次会返回相同问题，
    # 真实 LLM 实现中会生成不同的表述）
    question_update = await generate_question(state)
    state.update(question_update)
    new_msgs = question_update.get("messages", [])
    state["messages"].extend(new_msgs)

    question_text = state.get("current_question", "")
    point_id, _ = _get_current_point_info(state)

    await _save_message(
        db, session_id, "assistant", question_text, point_id,
    )

    # 获取 ORM 对象做 checkpoint
    orm_result = await db.execute(
        select(InterviewStateORM).where(
            InterviewStateORM.session_id == session_id
        )
    )
    state_orm = orm_result.scalar_one_or_none()
    if state_orm:
        await _save_state_checkpoint(db, state_orm, state)

    return {
        "code": 0,
        "message": "已换一种问法",
        "data": {
            "session_id": str(session_id),
            "question": question_text,
            "point_id": point_id,
            "round": state.get("current_round", 1),
        },
    }


@router.get(
    "/sessions/{session_id}/interview/resume",
    response_model=InterviewResumeResponse,
)
async def resume_interview(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """恢复面试（断点续传）

    返回当前面试的完整状态，包括消息历史和当前问题。
    """
    state = await _load_interview_state(db, session_id)
    if not state:
        raise HTTPException(status_code=404, detail={
            "code": 1002,
            "message": "面试未开始",
        })

    point_id, _ = _get_current_point_info(state)

    # 如果面试未结束，重新生成当前问题（确保 current_question 有值）
    current_question = None
    if not state.get("is_completed"):
        question_update = await generate_question(state)
        current_question = question_update.get("current_question", "")

    # 如果有报告，从 ORM 加载
    report = state.get("report")
    if not report and state.get("is_completed"):
        orm_result = await db.execute(
            select(InterviewStateORM).where(
                InterviewStateORM.session_id == session_id
            )
        )
        state_orm = orm_result.scalar_one_or_none()
        if state_orm and state_orm.report_json:
            try:
                report = json.loads(state_orm.report_json)
            except (json.JSONDecodeError, TypeError):
                pass

    doubt_points = state.get("doubt_points", [])
    point_states = state.get("point_states", {})

    return InterviewResumeResponse(
        session_id=str(session_id),
        current_point_index=state.get("current_point_index", 0),
        current_round=state.get("current_round", 1),
        point_states=point_states,
        messages=state.get("messages", []),
        is_completed=state.get("is_completed", False),
        report=report,
        total_points=len(doubt_points),
        current_question=current_question,
        current_point_id=point_id,
        point_list=_build_point_state_list(doubt_points, point_states),
    )


@router.post("/sessions/{session_id}/interview/end")
async def end_interview(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """结束面试并生成报告

    用户主动结束面试，用当前已有的评估数据生成报告。
    """
    state = await _load_interview_state(db, session_id)
    if not state:
        raise HTTPException(status_code=404, detail={
            "code": 1002,
            "message": "面试未开始",
        })

    if state.get("is_completed"):
        # 已完成，直接返回报告
        orm_result = await db.execute(
            select(InterviewStateORM).where(
                InterviewStateORM.session_id == session_id
            )
        )
        state_orm = orm_result.scalar_one_or_none()
        report = {}
        if state_orm and state_orm.report_json:
            try:
                report = json.loads(state_orm.report_json)
            except (json.JSONDecodeError, TypeError):
                pass
        return {
            "code": 0,
            "message": "面试已完成",
            "data": {
                "session_id": session_id,
                "status": "complete",
                "report": report,
            },
        }

    # 标记所有未处理的存疑点为 skipped
    doubt_points = state.get("doubt_points", [])
    point_states = dict(state.get("point_states", {}))
    for i, point in enumerate(doubt_points):
        pid = point.get("id", f"point_{i}")
        if point_states.get(pid) not in ("resolved", "skipped"):
            point_states[pid] = "skipped"

    state["point_states"] = point_states
    state["is_completed"] = True

    # 直接用规则生成报告（跳过 LLM，避免超时）
    from app.agent.nodes.report import _rule_generate_report
    report = _rule_generate_report(state)
    state["report"] = report
    state["is_completed"] = True

    # 保存到数据库
    await _save_message(
        db, session_id, "assistant",
        json.dumps(state.get("report", {}), ensure_ascii=False), "",
    )

    orm_result = await db.execute(
        select(InterviewStateORM).where(
            InterviewStateORM.session_id == session_id
        )
    )
    state_orm = orm_result.scalar_one_or_none()
    if state_orm:
        await _save_state_checkpoint(db, state_orm, state)

    # 更新 session 状态
    session_result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = session_result.scalar_one_or_none()
    if session:
        session.status = SessionStatus.COMPLETED
        session.updated_at = datetime.utcnow()

    await db.commit()

    return {
        "code": 0,
        "message": "面试已结束",
        "data": {
            "session_id": session_id,
            "status": "complete",
            "report": state.get("report"),
        },
    }
