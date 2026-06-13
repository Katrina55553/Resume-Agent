"""评估决策节点

评估用户回答质量，决定下一步：追问 / 切换存疑点 / 生成报告。
LLM 可用时调用 DeepSeek 进行智能评估，否则使用规则评分。
支持 Tool Calling：LLM 可自主调用知识库验证技术准确性。
"""

import json
import re
from typing import Any

from app.agent.rules import DEFAULT_RULES
from app.core.llm import (
    call_llm_with_tools,
    continue_with_tool_results,
    is_llm_available,
)
from app.core.tools import execute_tool, get_tools


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


# ---------- LLM 评估（Tool Calling）----------

_EVALUATE_SYSTEM_PROMPT = """你是一位技术面试评估专家。请评估候选人对面试问题的回答质量。

你可以使用以下工具：
- search_knowledge_base: 检索技术知识库，验证候选人回答中的技术描述是否准确
- verify_code_snippet: 当候选人给出了代码片段时，验证其正确性

评估维度：
1. 真实性 - 回答是否可信，有具体细节支撑
2. 深度 - 是否展示了对技术/业务的深入理解
3. 完整性 - 是否回答了问题的核心要点
4. 逻辑性 - 表达是否清晰、有条理
5. 技术准确性 - 回答中的技术描述是否正确

返回 JSON 格式：
{
  "score": 0-100（综合评分）,
  "feedback": "简短评语（50字以内）",
  "credible": true/false（回答是否可信）,
  "highlights": ["亮点1"],
  "weaknesses": ["不足1"]
}

评分标准：
- 90-100: 回答优秀，有具体案例和数据支撑，技术描述准确
- 70-89: 回答良好，基本可信但可补充细节
- 50-69: 回答一般，缺乏具体支撑
- 30-49: 回答较差，内容模糊或不可信
- 0-29: 回答很差，明显敷衍或跑题"""


def _llm_evaluate_answer(
    doubt_point: dict,
    question: str,
    answer: str,
    current_round: int,
    resume_data: dict = None,
) -> dict:
    """调用 LLM 评估回答（支持 Tool Calling）"""
    source_text = doubt_point.get("source_text", "")
    reason = doubt_point.get("reason", "")

    user_prompt = f"""存疑点：{source_text}
存疑原因：{reason}

面试官提问：{question}

候选人回答：{answer}

追问轮次：第 {current_round} 轮

请评估回答质量（如需验证技术准确性，可调用工具）："""

    # 第一次调用：带 tools
    content, tool_calls = call_llm_with_tools(
        _EVALUATE_SYSTEM_PROMPT, user_prompt, get_tools(), temperature=0.3,
    )

    # 如果没有工具调用，尝试解析 JSON
    if not tool_calls:
        if content:
            return _parse_evaluation(content)
        return None

    # 执行工具调用
    tool_results = []
    for tc in tool_calls:
        result = execute_tool(tc["name"], tc["arguments"], resume_data)
        tool_results.append({
            "tool_call_id": tc["id"],
            "content": result,
        })

    # 将工具结果返回给 LLM
    assistant_msg = {
        "role": "assistant",
        "content": content or "",
        "tool_calls": [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": str(tc["arguments"]),
                },
            }
            for tc in tool_calls
        ],
    }

    final_prompt_messages = [
        {"role": "user", "content": user_prompt},
        assistant_msg,
    ]

    final_result = continue_with_tool_results(
        _EVALUATE_SYSTEM_PROMPT, final_prompt_messages, tool_results, temperature=0.3,
    )

    if final_result:
        return _parse_evaluation(final_result)

    # 降级：用第一次的文本
    if content:
        return _parse_evaluation(content)
    return None


def _parse_evaluation(text: str) -> dict:
    """解析 LLM 返回的评估 JSON"""
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ---------- 节点函数 ----------


async def evaluate_answer(state: dict[str, Any]) -> dict[str, Any]:
    """评估用户回答并决定下一步"""
    answer_text: str = state.get("current_answer", "")
    current_round: int = state.get("current_round", 1)
    point_index: int = state.get("current_point_index", 0)
    doubt_points: list[dict] = state.get("doubt_points", [])
    point_states: dict = dict(state.get("point_states", {}))
    answer_too_short: bool = state.get("answer_too_short", False)
    messages: list[dict] = state.get("messages", [])
    resume_data: dict = state.get("resume_data", {})

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
            current_point, current_question, answer_text, current_round, resume_data,
        )

    if llm_result:
        score = llm_result.get("score", 60)
        feedback = llm_result.get("feedback", "")
        credible = llm_result.get("credible", True)
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

    return {
        "current_evaluation": evaluation,
        "decision": "follow_up",
        "current_round": current_round + 1,
        "point_states": point_states,
    }
