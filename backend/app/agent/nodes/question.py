"""追问生成节点

根据当前存疑点和对话历史生成面试问题。
LLM 可用时调用 DeepSeek，否则使用模板。
接入 RAG 知识库，检索相关面试题作为参考。
"""

from typing import Dict, Any, List

from app.core.llm import call_llm, is_llm_available
from app.core.rag import retrieve_context, extract_technical_keywords


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


# ---------- LLM 生成 ----------

_QUESTION_SYSTEM_PROMPT = """你是一位经验丰富的技术面试官，正在进行简历真实性验证面试。

你的任务是根据当前存疑点和对话历史，生成下一个面试问题。

规则：
- 问题要具体、有针对性，能验证简历内容的真实性
- 不要重复之前问过的问题
- 如果是第一轮提问，从存疑点的核心入手
- 如果是追问，根据用户的上一个回答深入挖掘
- 参考知识库中的面试题，但要根据候选人的简历内容做针对性调整
- 语气自然，像真实面试对话，不要太生硬
- 只返回问题文本，不要其他内容"""


def _llm_generate_question(
    doubt_point: dict,
    messages: List[dict],
    current_round: int,
) -> str:
    """调用 LLM 生成问题（增强 RAG 上下文）"""
    # 构建对话历史（最近 6 轮）
    recent_messages = messages[-12:] if len(messages) > 12 else messages
    history_text = "\n".join(
        f"{'面试官' if m['role'] == 'assistant' else '候选人'}: {m['content']}"
        for m in recent_messages
    )

    # RAG 检索：从知识库中查找相关面试题
    source_text = doubt_point.get("source_text", "")
    reason = doubt_point.get("reason", "")
    keywords = extract_technical_keywords(f"{source_text} {reason}")
    rag_query = " ".join(keywords) if keywords else f"{source_text} {reason}"
    rag_context = retrieve_context(rag_query, top_k=3)

    # 构建 prompt
    rag_section = ""
    if rag_context:
        rag_section = f"""
参考知识（面试题库，可参考但需结合简历内容调整）：
{rag_context}

"""

    user_prompt = f"""{rag_section}当前存疑点：
- 原文引用：{source_text}
- 存疑原因：{reason}
- 追问轮次：第 {current_round} 轮

对话历史：
{history_text if history_text else '（刚开始面试）'}

请生成下一个面试问题："""

    result = call_llm(_QUESTION_SYSTEM_PROMPT, user_prompt, temperature=0.7)
    if result:
        return result.strip().strip('"').strip("'")
    return None


# ---------- 节点函数 ----------


async def generate_question(state: Dict[str, Any]) -> Dict[str, Any]:
    """生成面试问题

    从 state 的 doubt_points 中取 current_point_index 对应的存疑点，
    根据 current_round 决定是首轮提问还是追问。
    """
    doubt_points: List[dict] = state.get("doubt_points", [])
    point_index: int = state.get("current_point_index", 0)
    current_round: int = state.get("current_round", 1)
    messages: List[dict] = list(state.get("messages", []))

    if not doubt_points or point_index >= len(doubt_points):
        return {
            "current_question": None,
            "messages": messages,
        }

    current_point = doubt_points[point_index]

    # 优先用 LLM，降级到模板
    question_text = None
    if is_llm_available():
        question_text = _llm_generate_question(current_point, messages, current_round)

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
