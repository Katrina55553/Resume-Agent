"""报告生成节点

汇总所有对话和评估，生成最终面试报告。
LLM 可用时调用 DeepSeek 生成个性化报告，否则使用规则生成。
"""

import asyncio
import json
import logging
from typing import Dict, Any, List

from app.core.llm import call_llm_json, is_llm_available

logger = logging.getLogger(__name__)


# ---------- 规则报告（降级方案）----------

def _compute_overall_score(evaluations: List[dict]) -> int:
    """根据所有评估结果计算综合得分"""
    if not evaluations:
        return 0
    scores = [e.get("score", 0) for e in evaluations]
    return round(sum(scores) / len(scores))


def _extract_point_feedback(
    doubt_points: List[dict],
    point_states: dict,
    evaluations: List[dict],
) -> List[dict]:
    """为每个存疑点生成逐点反馈"""
    feedbacks = []
    for i, point in enumerate(doubt_points):
        pid = point.get("id", f"point_{i}")
        state = point_states.get(pid, "pending")
        related_evals = [e for e in evaluations if e.get("point_index") == i]
        avg_score = 0
        if related_evals:
            avg_score = round(sum(e.get("score", 0) for e in related_evals) / len(related_evals))

        if state == "skipped":
            fb = "该存疑点被跳过，建议在简历中补充相关说明。"
        elif avg_score >= 75:
            fb = "回答充分，该存疑点已消除。"
        elif avg_score >= 55:
            fb = "回答基本合理，但建议在简历中补充更多细节。"
        else:
            fb = "回答未能充分解释该存疑点，建议修改简历相关内容。"

        feedbacks.append({
            "point_id": pid,
            "source_text": point.get("source_text", ""),
            "state": state,
            "score": avg_score,
            "feedback": fb,
        })
    return feedbacks


def _rule_generate_report(state: dict) -> dict:
    """规则生成报告（降级方案）"""
    doubt_points = state.get("doubt_points", [])
    point_states = state.get("point_states", {})
    evaluations = state.get("evaluations", [])

    overall_score = _compute_overall_score(evaluations)
    point_feedbacks = _extract_point_feedback(doubt_points, point_states, evaluations)

    resolved = sum(1 for f in point_feedbacks if f["state"] == "resolved")
    skipped = sum(1 for f in point_feedbacks if f["state"] == "skipped")

    suggestions = []
    weak_points = [f for f in point_feedbacks if f["score"] < 60]
    if weak_points:
        suggestions.append(f"有 {len(weak_points)} 个存疑点回答较弱，建议重点完善简历中相关内容。")
    if skipped:
        suggestions.append(f"有 {len(skipped)} 个存疑点被跳过，建议补充相关经历描述。")
    if overall_score >= 80:
        suggestions.append("整体表现优秀，简历内容可信度高。")
    elif overall_score >= 60:
        suggestions.append("表现中等，部分经历描述可以更具体。")
    else:
        suggestions.append("建议重新审视简历内容，确保所有描述都有充分的事实支撑。")
    suggestions.append("建议在面试前针对薄弱环节准备具体案例和数据。")

    return {
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


# ---------- LLM 报告 ----------

_REPORT_SYSTEM_PROMPT = """你是简历面试评估专家。请根据面试过程中的所有对话和评估数据，生成一份详细的面试评估报告。

返回 JSON 格式：
{
  "overall_score": 0-100,
  "total_points": 存疑点总数,
  "resolved_points": 已解决数,
  "skipped_points": 跳过数,
  "point_feedbacks": [
    {
      "point_id": "存疑点ID",
      "source_text": "原文引用",
      "state": "resolved|skipped|pending",
      "score": 0-100,
      "feedback": "针对该存疑点的详细评语（50-100字）"
    }
  ],
  "suggestions": ["具体改进建议1", "建议2", "建议3"],
  "summary": "整体评估摘要（100-200字，包含亮点和不足）"
}

要求：
- 只返回 JSON
- point_feedbacks 的 feedback 要具体，指出回答的亮点或不足
- suggestions 要可操作，不要泛泛而谈
- summary 要客观、专业"""


def _llm_generate_report(state: dict) -> dict:
    """调用 LLM 生成报告"""
    doubt_points = state.get("doubt_points", [])
    point_states = state.get("point_states", {})
    evaluations = state.get("evaluations", [])
    messages = state.get("messages", [])

    # 构建对话摘要
    conversation = "\n".join(
        f"{'面试官' if m['role'] == 'assistant' else '候选人'}: {m['content'][:200]}"
        for m in messages[-20:]
    )

    # 构建评估数据
    eval_summary = json.dumps(evaluations, ensure_ascii=False)

    # 构建存疑点状态
    points_info = []
    for i, point in enumerate(doubt_points):
        pid = point.get("id", f"point_{i}")
        points_info.append({
            "id": pid,
            "source_text": point.get("source_text", ""),
            "reason": point.get("reason", ""),
            "state": point_states.get(pid, "pending"),
        })

    user_prompt = f"""存疑点列表：
{json.dumps(points_info, ensure_ascii=False, indent=2)}

评估记录：
{eval_summary}

对话摘要：
{conversation}

请生成面试评估报告："""

    result = call_llm_json(_REPORT_SYSTEM_PROMPT, user_prompt, max_tokens=4096)
    if result and "overall_score" in result:
        return result
    return None


# ---------- 节点函数 ----------


async def generate_report(state: Dict[str, Any]) -> Dict[str, Any]:
    """生成面试报告

    汇总所有对话和评估结果，生成最终报告。
    LLM 调用限时 30 秒，超时自动降级到规则报告。
    """
    report = None

    if is_llm_available():
        try:
            loop = asyncio.get_running_loop()
            report = await asyncio.wait_for(
                loop.run_in_executor(None, _llm_generate_report, state),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.warning("LLM 报告生成超时（30s），降级到规则报告")
            report = None
        except Exception as e:
            logger.error(f"LLM 报告生成异常: {e}", exc_info=True)
            report = None

    if report is None:
        report = _rule_generate_report(state)

    return {
        "report": report,
        "is_completed": True,
    }
