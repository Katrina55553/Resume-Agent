"""回答收集节点

处理和验证用户回答。
"""

from typing import Dict, Any


async def collect_answer(state: Dict[str, Any]) -> Dict[str, Any]:
    """收集和处理用户回答

    Args:
        state: Agent 状态

    Returns:
        更新后的状态
    """
    # TODO: 实现回答收集逻辑
    # 1. 验证回答长度和格式
    # 2. 添加到消息历史
    # 3. 更新 token 计数
    return {
        **state,
        "current_answer": state.get("current_answer", ""),
    }
