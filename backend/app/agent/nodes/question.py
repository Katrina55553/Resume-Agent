"""追问生成节点

根据当前存疑点和对话历史生成面试问题。
当前使用 mock 实现，后续替换为真实 Claude API 调用。
"""

from typing import Dict, Any, List


# ---------- mock LLM 问题生成 ----------

_INTRO_TEMPLATES = [
    "我看到你简历中提到「{source}」，能详细说说这段经历吗？",
    "关于「{source}」这部分，能否展开讲讲你具体做了什么？",
    "简历里写了「{source}」，可以给我介绍一下背景和你的角色吗？",
]

_FOLLOWUP_TEMPLATES = [
    "你说的这个能再具体一些吗？比如遇到过什么挑战？",
    "那在这个过程中，你是怎么解决遇到的困难的？",
    "能举一个具体的例子来说明吗？",
]


def _mock_generate_initial_question(doubt_point: dict) -> str:
    """为存疑点生成第一轮问题（mock）。

    优先使用存疑点自带的 probe_questions[0]，
    如果没有则使用模板生成。
    """
    probes: List[str] = doubt_point.get("probe_questions", [])
    if probes:
        return probes[0]

    source = doubt_point.get("source_text", "这段经历")
    idx = hash(doubt_point.get("id", "")) % len(_INTRO_TEMPLATES)
    return _INTRO_TEMPLATES[idx].format(source=source[:30])


def _mock_generate_followup_question(
    doubt_point: dict,
    messages: List[dict],
    current_round: int,
) -> str:
    """生成追问问题（mock）。

    根据轮次选择 probe_questions 中后续的问题，
    或使用追问模板。
    """
    probes: List[str] = doubt_point.get("probe_questions", [])
    # probe_questions 索引从 0 开始，round 从 1 开始
    probe_idx = current_round - 1
    if probe_idx < len(probes):
        return probes[probe_idx]

    idx = (current_round - 1) % len(_FOLLOWUP_TEMPLATES)
    return _FOLLOWUP_TEMPLATES[idx]


# ---------- 节点函数 ----------


async def generate_question(state: Dict[str, Any]) -> Dict[str, Any]:
    """生成面试问题

    从 state 的 doubt_points 中取 current_point_index 对应的存疑点，
    根据 current_round 决定是首轮提问还是追问。

    Args:
        state: Agent 状态，必须包含:
            - doubt_points: 存疑点列表
            - current_point_index: 当前存疑点索引
            - current_round: 当前追问轮次
            - messages: 消息历史

    Returns:
        状态更新字典，包含 current_question 和更新后的 messages。
    """
    doubt_points: List[dict] = state.get("doubt_points", [])
    point_index: int = state.get("current_point_index", 0)
    current_round: int = state.get("current_round", 1)
    messages: List[dict] = list(state.get("messages", []))

    # 边界保护
    if not doubt_points or point_index >= len(doubt_points):
        return {
            "current_question": None,
            "messages": messages,
        }

    current_point = doubt_points[point_index]

    # 根据轮次生成问题
    if current_round <= 1:
        question_text = _mock_generate_initial_question(current_point)
    else:
        question_text = _mock_generate_followup_question(
            current_point, messages, current_round,
        )

    # 构造消息记录
    question_msg = {
        "role": "assistant",
        "content": question_text,
        "point_id": current_point.get("id", ""),
        "round": current_round,
    }

    return {
        "current_question": question_text,
        "messages": [question_msg],  # Annotated[List, add] reducer 会 append
    }
