"""评估决策节点

评估用户回答质量，决定下一步：追问 / 切换存疑点 / 生成报告。
LLM 可用时调用 DeepSeek 进行智能评估，否则使用规则评分。
"""

from typing import Dict, Any, List

from app.core.llm import call_llm_json, is_llm_available
from app.agent.rules import DEFAULT_RULES


# ---------- 规则评分（降级方案）----------

def _rule_score_answer(answer_text: str, current_round: int) -> tuple:
    """规则评分，返回 (score, feedback)"""
    length = len(answer_text.strip())
    round_bonus = min(current_round * 3, 15)

    if length < DEFAULT_RULES.MIN_ANSWER_LENGTH:
        score = min(35 + round_bonus, 100)
        feedback = "回答过于简略，建议结合具体经历展开说明。"
    elif length < 200:
        score = min(60 + round_bonus, 100)
        feedback = "回答基本清楚，但可以补充更多细节和具体案例。"
    else:
        score = min(75 + round_bonus, 100)
        feedback = "回答详细，逻辑清晰，有具体案例支撑。"

    return score, feedback


# ---------- LLM 评估 ----------

_EVALUATE_SYSTEM_PROMPT = """你是一位技术面试评估专家。请评估候选人对面试问题的回答质量。

评估维度：
1. 真实性 - 回答是否可信，有具体细节支撑
2. 深度 - 是否展示了对技术/业务的深入理解
3. 完整性 - 是否回答了问题的核心要点
4. 逻辑性 - 表达是否清晰、有条理

返回 JSON 格式：
{
  "score": 0-100（综合评分）,
  "feedback": "简短评语（30字以内）",
  "credible": true/false（回答是否可信）,
  "highlights": ["亮点1"],
  "weaknesses": ["不足1"]
}

评分标准：
- 90-100: 回答优秀，有具体案例和数据支撑
- 70-89: 回答良好，基本可信但可补充细节
- 50-69: 回答一般，缺乏具体支撑
- 30-49: 回答较差，内容模糊或不可信
- 0-29: 回答很差，明显敷衍或跑题"""


def _llm_evaluate_answer(
    doubt_point: dict,
    question: str,
    answer: str,
    current_round: int,
) -> dict:
    """调用 LLM 评估回答"""
    user_prompt = f"""存疑点：{doubt_point.get('source_text', '')}
存疑原因：{doubt_point.get('reason', '')}

面试官提问：{question}

候选人回答：{answer}

追问轮次：第 {current_round} 轮

请评估回答质量："""

    result = call_llm_json(_EVALUATE_SYSTEM_PROMPT, user_prompt)
    if result and "score" in result:
        return result
    return None


# ---------- 节点函数 ----------


async def evaluate_answer(state: Dict[str, Any]) -> Dict[str, Any]:
    """评估用户回答并决定下一步

    决策逻辑：
    1. 如果 current_round >= MAX_FOLLOW_UP → 标记当前点 resolved，切换到下一个
    2. 如果回答质量低且轮次未满 → follow_up（继续追问）
    3. 如果所有存疑点都处理完 → 生成报告
    """
    answer_text: str = state.get("current_answer", "")
    current_round: int = state.get("current_round", 1)
    point_index: int = state.get("current_point_index", 0)
    doubt_points: List[dict] = state.get("doubt_points", [])
    point_states: dict = dict(state.get("point_states", {}))
    answer_too_short: bool = state.get("answer_too_short", False)
    messages: List[dict] = state.get("messages", [])

    # 获取当前存疑点和问题
    current_point = doubt_points[point_index] if point_index < len(doubt_points) else {}
    current_question = ""
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            current_question = msg.get("content", "")
            break

    # 评估
    llm_result = None
    if is_llm_available() and len(answer_text.strip()) >= 10:
        llm_result = _llm_evaluate_answer(
            current_point, current_question, answer_text, current_round,
        )

    if llm_result:
        score = llm_result.get("score", 60)
        feedback = llm_result.get("feedback", "")
        credible = llm_result.get("credible", True)
        # 不可信的回答降分
        if not credible:
            score = min(score, 45)
    else:
        score, feedback = _rule_score_answer(answer_text, current_round)

    if answer_too_short:
        score = min(score, 40)
        feedback = "回答过于简略，" + feedback

    evaluation = {
        "score": score,
        "feedback": feedback,
        "round": current_round,
        "point_index": point_index,
    }

    # 决策
    current_point_id = ""
    if doubt_points and point_index < len(doubt_points):
        current_point_id = doubt_points[point_index].get("id", "")

    # 追问次数达到上限，或回答质量足够高 → 切换到下一个存疑点
    if current_round >= DEFAULT_RULES.MAX_FOLLOW_UP or score >= 75:
        if current_point_id:
            point_states[current_point_id] = "resolved"

        next_index = point_index + 1

        if next_index >= len(doubt_points):
            return {
                "current_evaluation": evaluation,
                "decision": "report",
                "point_states": point_states,
                "is_completed": True,
            }

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
