"""追问生成节点

根据当前存疑点和对话历史生成面试问题。
LLM 可用时调用 DeepSeek（支持 Tool Calling），否则使用模板。
LLM 可自主决定调用知识库检索、查看简历字段、验证代码。
"""

from typing import Dict, Any, List

from app.core.llm import (
    call_llm,
    call_llm_with_tools,
    continue_with_tool_results,
    is_llm_available,
)
from app.core.tools import get_tools, execute_tool


# ---------- 模板（降级方案）----------

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


def _template_question(doubt_point: dict, current_round: int) -> str:
    """模板生成问题（降级方案）"""
    probes: List[str] = doubt_point.get("probe_questions", [])
    probe_idx = current_round - 1
    if probe_idx < len(probes):
        return probes[probe_idx]

    source = doubt_point.get("source_text", "这段经历")
    if current_round <= 1:
        idx = hash(doubt_point.get("id", "")) % len(_INTRO_TEMPLATES)
        return _INTRO_TEMPLATES[idx].format(source=source[:30])
    else:
        idx = (current_round - 1) % len(_FOLLOWUP_TEMPLATES)
        return _FOLLOWUP_TEMPLATES[idx]


# ---------- LLM 生成（Tool Calling）----------

_QUESTION_SYSTEM_PROMPT = """你是一位经验丰富的技术面试官，正在进行简历真实性验证面试。

你的任务是根据当前存疑点和对话历史，生成下一个面试问题。

你可以使用以下工具：
- search_knowledge_base: 从面试题库中检索相关技术资料，用于生成更专业的问题
- lookup_resume_field: 查看候选人简历的具体字段，用于引用简历内容提问
- verify_code_snippet: 当候选人给出了代码片段时，验证其正确性

规则：
- 问题要具体、有针对性，能验证简历内容的真实性
- 不要重复之前问过的问题
- 如果是第一轮提问，从存疑点的核心入手
- 如果是追问，根据用户的上一个回答深入挖掘
- 需要技术参考资料时，主动调用 search_knowledge_base
- 需要确认简历细节时，主动调用 lookup_resume_field
- 语气自然，像真实面试对话，不要太生硬
- 最终只返回问题文本，不要其他内容"""


def _llm_generate_question(
    doubt_point: dict,
    messages: List[dict],
    current_round: int,
    resume_data: dict = None,
) -> str:
    """调用 LLM 生成问题（支持 Tool Calling）"""
    # 构建对话历史
    recent_messages = messages[-12:] if len(messages) > 12 else messages
    history_text = "\n".join(
        f"{'面试官' if m['role'] == 'assistant' else '候选人'}: {m['content']}"
        for m in recent_messages
    )

    source_text = doubt_point.get("source_text", "")
    reason = doubt_point.get("reason", "")

    user_prompt = f"""当前存疑点：
- 原文引用：{source_text}
- 存疑原因：{reason}
- 追问轮次：第 {current_round} 轮

对话历史：
{history_text if history_text else '（刚开始面试）'}

请生成下一个面试问题："""

    # 第一次调用：带 tools
    content, tool_calls = call_llm_with_tools(
        _QUESTION_SYSTEM_PROMPT, user_prompt, get_tools(), temperature=0.7,
    )

    # 如果没有工具调用，直接返回文本
    if not tool_calls:
        if content:
            return content.strip().strip('"').strip("'")
        return None

    # 执行工具调用
    tool_results = []
    for tc in tool_calls:
        result = execute_tool(tc["name"], tc["arguments"], resume_data)
        tool_results.append({
            "tool_call_id": tc["id"],
            "content": result,
        })

    # 将工具结果返回给 LLM，获取最终问题
    # 构建 assistant 消息（包含 tool_calls）
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
        _QUESTION_SYSTEM_PROMPT, final_prompt_messages, tool_results, temperature=0.7,
    )

    if final_result:
        return final_result.strip().strip('"').strip("'")

    # 降级：用第一次的文本回复
    if content:
        return content.strip().strip('"').strip("'")
    return None


# ---------- 节点函数 ----------


async def generate_question(state: Dict[str, Any]) -> Dict[str, Any]:
    """生成面试问题"""
    doubt_points: List[dict] = state.get("doubt_points", [])
    point_index: int = state.get("current_point_index", 0)
    current_round: int = state.get("current_round", 1)
    messages: List[dict] = list(state.get("messages", []))
    resume_data: dict = state.get("resume_data", {})

    if not doubt_points or point_index >= len(doubt_points):
        return {
            "current_question": None,
            "messages": messages,
        }

    current_point = doubt_points[point_index]

    # 优先用 LLM（带 Tool Calling），降级到模板
    question_text = None
    if is_llm_available():
        question_text = _llm_generate_question(
            current_point, messages, current_round, resume_data,
        )

    if question_text is None:
        question_text = _template_question(current_point, current_round)

    question_msg = {
        "role": "assistant",
        "content": question_text,
        "point_id": current_point.get("id", ""),
        "round": current_round,
    }

    return {
        "current_question": question_text,
        "messages": [question_msg],
    }
