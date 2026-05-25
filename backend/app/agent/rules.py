"""面试规则引擎

定义面试过程中的规则和约束，防止死循环和异常行为。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class InterviewRules:
    """面试规则配置

    使用 frozen dataclass 确保规则不可变。
    """
    # 最大追问次数（同一问题）
    MAX_FOLLOW_UP: int = 3

    # 最大错误次数（LLM 异常、超时等）
    MAX_ERROR_COUNT: int = 3

    # LLM 超时时间（秒）
    LLM_TIMEOUT: int = 15

    # 单次会话最大 Token 数
    MAX_TOKENS_PER_SESSION: int = 50000

    # 最大问题总数
    MAX_QUESTIONS: int = 20

    # 单个回答最大长度（字符）
    MAX_ANSWER_LENGTH: int = 5000

    # 最小回答长度（太短的回答需要追问）
    MIN_ANSWER_LENGTH: int = 50


# 默认规则实例
DEFAULT_RULES = InterviewRules()


def should_force_switch(
    follow_up_count: int,
    error_count: int,
    total_tokens: int,
    question_count: int,
    rules: InterviewRules = DEFAULT_RULES,
) -> tuple[bool, Optional[str]]:
    """判断是否需要强制切换话题或结束面试

    Args:
        follow_up_count: 当前问题追问次数
        error_count: 错误次数
        total_tokens: 已用 Token 数
        question_count: 已问问题数
        rules: 规则配置

    Returns:
        (是否强制切换, 原因)
    """
    # 追问次数超限
    if follow_up_count >= rules.MAX_FOLLOW_UP:
        return True, "追问次数已达上限，切换到下一个问题"

    # 错误次数超限
    if error_count >= rules.MAX_ERROR_COUNT:
        return True, "错误次数过多，结束面试"

    # Token 数超限
    if total_tokens >= rules.MAX_TOKENS_PER_SESSION:
        return True, "Token 数已达上限，结束面试"

    # 问题数超限
    if question_count >= rules.MAX_QUESTIONS:
        return True, "问题数已达上限，结束面试"

    return False, None
