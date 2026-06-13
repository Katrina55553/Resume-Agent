"""回答收集节点

处理用户回答：验证、记录到消息列表。
"""

from typing import Any

from app.agent.rules import DEFAULT_RULES


async def collect_answer(state: dict[str, Any]) -> dict[str, Any]:
    """收集和处理用户回答

    将用户回答添加到消息列表，返回状态更新。
    current_round 的递增由调用方（API 层）在评估后处理，
    以便在同一请求中协调多个节点。

    Args:
        state: Agent 状态，必须包含:
            - current_answer: 用户回答文本
            - current_point_index: 当前存疑点索引
            - doubt_points: 存疑点列表
            - current_round: 当前轮次

    Returns:
        状态更新字典，包含更新后的 messages。
    """
    answer_text: str = state.get("current_answer", "")
    doubt_points: list[dict] = state.get("doubt_points", [])
    point_index: int = state.get("current_point_index", 0)

    # 获取当前存疑点 ID（用于消息关联）
    point_id = ""
    if doubt_points and point_index < len(doubt_points):
        point_id = doubt_points[point_index].get("id", "")

    # 回答过短时记录一条提示消息（但仍保存用户回答）
    answer_too_short = len(answer_text.strip()) < DEFAULT_RULES.MIN_ANSWER_LENGTH

    user_msg = {
        "role": "user",
        "content": answer_text,
        "point_id": point_id,
    }

    result = {
        "messages": [user_msg],
    }

    # 如果回答过短，追加一条系统提示（不计入消息历史，
    # 但让后续评估节点知道需要追问）
    if answer_too_short:
        result["answer_too_short"] = True

    return result
