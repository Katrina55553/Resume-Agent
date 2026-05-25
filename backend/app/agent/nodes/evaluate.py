"""评估决策节点

评估用户回答并决定下一步行动。
"""

from typing import Dict, Any


async def evaluate_answer(state: Dict[str, Any]) -> Dict[str, Any]:
    """评估用户回答

    根据回答质量决定：
    - 继续追问
    - 切换话题
    - 结束面试

    Args:
        state: Agent 状态

    Returns:
        更新后的状态（包含评估结果和决策）
    """
    # TODO: 实现评估逻辑
    # 1. 调用 LLM 评估回答质量
    # 2. 判断是否需要追问
    # 3. 检查是否需要切换话题
    # 4. 应用规则引擎
    return {
        **state,
        "current_evaluation": {
            "score": 70,
            "feedback": "placeholder-feedback",
        },
        "should_switch_topic": False,
        "force_end": False,
    }
