"""评估决策节点

评估用户回答质量，决定下一步：追问 / 切换存疑点 / 生成报告。
当前使用 mock 实现，后续替换为真实 LLM 评估。
"""

from typing import Dict, Any, List

from app.agent.rules import DEFAULT_RULES


# ---------- mock 评分 ----------

def _mock_score_answer(answer_text: str, current_round: int) -> int:
    """模拟回答质量评分（0-100）。

    简单规则：
    - 回答太短（<50 字）→ 30-40 分
    - 中等长度（50-200 字）→ 55-70 分
    - 详细回答（>200 字）→ 70-90 分
    追问轮次越高，基础分略有提升（用户有更多机会补充）。
    """
    length = len(answer_text.strip())
    round_bonus = min(current_round * 3, 15)

    if length < DEFAULT_RULES.MIN_ANSWER_LENGTH:
        return min(35 + round_bonus, 100)
    elif length < 200:
        return min(60 + round_bonus, 100)
    else:
        return min(75 + round_bonus, 100)


def _mock_generate_feedback(score: int) -> str:
    """根据评分生成简短反馈（mock）。"""
    if score >= 75:
        return "回答详细，逻辑清晰，有具体案例支撑。"
    elif score >= 55:
        return "回答基本清楚，但可以补充更多细节和具体案例。"
    else:
        return "回答过于简略，建议结合具体经历展开说明。"


# ---------- 节点函数 ----------


async def evaluate_answer(state: Dict[str, Any]) -> Dict[str, Any]:
    """评估用户回答并决定下一步

    决策逻辑：
    1. 如果 current_round >= MAX_FOLLOW_UP → 标记当前点 resolved，切换到下一个
    2. 如果回答质量低且轮次未满 → follow_up（继续追问）
    3. 如果所有存疑点都处理完 → 生成报告

    Args:
        state: Agent 状态，必须包含:
            - current_answer: 用户回答
            - current_round: 当前轮次
            - current_point_index: 当前存疑点索引
            - doubt_points: 存疑点列表
            - point_states: 各存疑点状态

    Returns:
        状态更新字典，包含:
        - current_evaluation: 评分和反馈
        - decision: "follow_up" | "next_point" | "report"
        - current_point_index: 更新后的索引（切换时）
        - current_round: 更新后的轮次
        - point_states: 更新后的存疑点状态
        - is_completed: 是否面试结束
    """
    answer_text: str = state.get("current_answer", "")
    current_round: int = state.get("current_round", 1)
    point_index: int = state.get("current_point_index", 0)
    doubt_points: List[dict] = state.get("doubt_points", [])
    point_states: dict = dict(state.get("point_states", {}))
    answer_too_short: bool = state.get("answer_too_short", False)

    # 1. 评分
    score = _mock_score_answer(answer_text, current_round)
    if answer_too_short:
        score = min(score, 40)

    feedback = _mock_generate_feedback(score)

    evaluation = {
        "score": score,
        "feedback": feedback,
        "round": current_round,
    }

    # 2. 决策
    # 当前存疑点 ID
    current_point_id = ""
    if doubt_points and point_index < len(doubt_points):
        current_point_id = doubt_points[point_index].get("id", "")

    # 追问次数达到上限，或回答质量足够高 → 切换到下一个存疑点
    if current_round >= DEFAULT_RULES.MAX_FOLLOW_UP or score >= 75:
        # 标记当前点为 resolved
        if current_point_id:
            point_states[current_point_id] = "resolved"

        next_index = point_index + 1

        # 检查是否所有存疑点都处理完
        if next_index >= len(doubt_points):
            return {
                "current_evaluation": evaluation,
                "decision": "report",
                "point_states": point_states,
                "is_completed": True,
            }

        # 切换到下一个存疑点
        # 标记下一个点为 active
        next_point_id = doubt_points[next_index].get("id", "")
        point_states[next_point_id] = "active"

        return {
            "current_evaluation": evaluation,
            "decision": "next_point",
            "current_point_index": next_index,
            "current_round": 1,
            "point_states": point_states,
        }

    # 回答不够好，继续追问
    return {
        "current_evaluation": evaluation,
        "decision": "follow_up",
        "current_round": current_round + 1,
        "point_states": point_states,
    }
