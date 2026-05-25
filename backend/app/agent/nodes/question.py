"""追问生成节点

根据简历和面试状态生成问题。
"""

from typing import Dict, Any


async def generate_question(state: Dict[str, Any]) -> Dict[str, Any]:
    """生成面试问题

    根据当前面试阶段、简历内容和历史对话生成下一个问题。

    Args:
        state: Agent 状态

    Returns:
        更新后的状态（包含新问题）
    """
    # TODO: 实现问题生成逻辑
    # 1. 根据 phase 确定问题类型
    # 2. 考虑 doubt_points 生成针对性问题
    # 3. 调用 LLM 生成问题
    return {
        **state,
        "current_question": "placeholder-question",
    }
