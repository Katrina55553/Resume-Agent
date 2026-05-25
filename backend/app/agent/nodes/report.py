"""报告生成节点

汇总所有对话和评估，生成最终面试报告。
当前使用 mock 实现，后续替换为真实 LLM 生成。
"""

import json
from typing import Dict, Any, List


def _compute_overall_score(evaluations: List[dict]) -> int:
    """根据所有评估结果计算综合得分。"""
    if not evaluations:
        return 0
    scores = [e.get("score", 0) for e in evaluations]
    return round(sum(scores) / len(scores))


def _extract_point_feedback(
    doubt_points: List[dict],
    point_states: dict,
    evaluations: List[dict],
) -> List[dict]:
    """为每个存疑点生成逐点反馈。"""
    feedbacks = []
    for i, point in enumerate(doubt_points):
        pid = point.get("id", f"point_{i}")
        state = point_states.get(pid, "pending")
        # 取该存疑点相关的评估（简化：按索引对应）
        related_evals = [
            e for e in evaluations
            if e.get("point_index") == i
        ]
        avg_score = 0
        if related_evals:
            avg_score = round(
                sum(e.get("score", 0) for e in related_evals) / len(related_evals)
            )

        feedbacks.append({
            "point_id": pid,
            "source_text": point.get("source_text", ""),
            "state": state,
            "score": avg_score,
            "feedback": _point_feedback_text(state, avg_score),
        })
    return feedbacks


def _point_feedback_text(state: str, score: int) -> str:
    """根据存疑点状态和得分生成反馈文本。"""
    if state == "skipped":
        return "该存疑点被跳过，建议在简历中补充相关说明。"
    if score >= 75:
        return "回答充分，该存疑点已消除。"
    if score >= 55:
        return "回答基本合理，但建议在简历中补充更多细节。"
    return "回答未能充分解释该存疑点，建议修改简历相关内容。"


def _generate_suggestions(
    point_feedbacks: List[dict],
    overall_score: int,
) -> List[str]:
    """根据逐点反馈生成改进建议。"""
    suggestions = []

    weak_points = [f for f in point_feedbacks if f["score"] < 60]
    if weak_points:
        suggestions.append(
            f"有 {len(weak_points)} 个存疑点回答较弱，建议重点完善简历中相关内容。"
        )

    skipped = [f for f in point_feedbacks if f["state"] == "skipped"]
    if skipped:
        suggestions.append(
            f"有 {len(skipped)} 个存疑点被跳过，建议补充相关经历描述。"
        )

    if overall_score >= 80:
        suggestions.append("整体表现优秀，简历内容可信度高。")
    elif overall_score >= 60:
        suggestions.append("表现中等，部分经历描述可以更具体。")
    else:
        suggestions.append("建议重新审视简历内容，确保所有描述都有充分的事实支撑。")

    suggestions.append("建议在面试前针对薄弱环节准备具体案例和数据。")

    return suggestions


async def generate_report(state: Dict[str, Any]) -> Dict[str, Any]:
    """生成面试报告

    汇总所有对话和评估结果，生成最终报告。

    Args:
        state: Agent 状态，应包含:
            - doubt_points: 存疑点列表
            - point_states: 各存疑点处理状态
            - messages: 完整消息历史
            - evaluations: 所有评估结果（由 API 层累积）

    Returns:
        状态更新字典，包含 report。
    """
    doubt_points: List[dict] = state.get("doubt_points", [])
    point_states: dict = state.get("point_states", {})
    evaluations: List[dict] = state.get("evaluations", [])

    overall_score = _compute_overall_score(evaluations)
    point_feedbacks = _extract_point_feedback(
        doubt_points, point_states, evaluations,
    )
    suggestions = _generate_suggestions(point_feedbacks, overall_score)

    # 统计
    resolved = sum(1 for f in point_feedbacks if f["state"] == "resolved")
    skipped = sum(1 for f in point_feedbacks if f["state"] == "skipped")

    report = {
        "overall_score": overall_score,
        "total_points": len(doubt_points),
        "resolved_points": resolved,
        "skipped_points": skipped,
        "point_feedbacks": point_feedbacks,
        "suggestions": suggestions,
        "summary": (
            f"本次面试共涉及 {len(doubt_points)} 个存疑点，"
            f"其中 {resolved} 个已充分解答，{skipped} 个被跳过。"
            f"综合得分 {overall_score}/100。"
        ),
    }

    return {
        "report": report,
        "is_completed": True,
    }
