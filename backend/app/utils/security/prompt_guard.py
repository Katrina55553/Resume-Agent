"""Prompt 注入防护

检测和防御 Prompt 注入攻击。
"""

import re

# 常见的 Prompt 注入模式
INJECTION_PATTERNS = [
    # 角色扮演注入
    r"ignore\s+(?:all\s+)?previous\s+instructions",
    r"you\s+are\s+now\s+(?:a|an)\s+",
    r"pretend\s+(?:you|that)\s+(?:are|is)\s+",
    r"act\s+as\s+(?:a|an)\s+",

    # 指令覆盖
    r"disregard\s+(?:all\s+)?(?:previous|prior)\s+",
    r"forget\s+(?:all\s+)?(?:previous|prior)\s+",
    r"override\s+(?:all\s+)?(?:previous|prior)\s+",

    # 系统提示泄露
    r"(?:show|reveal|display|print)\s+(?:me\s+)?(?:your|the)\s+(?:system|initial)\s+(?:prompt|instructions)",
    r"what\s+(?:are|is)\s+(?:your|the)\s+(?:system|initial)\s+(?:prompt|instructions)",

    # 编码绕过
    r"base64\s+(?:decode|encode)",
    r"rot13",
    r"\\x[0-9a-fA-F]{2}",

    # 越狱尝试
    r"jailbreak",
    r"DAN\s+mode",
    r"do\s+anything\s+now",
]

# 编译正则表达式
COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in INJECTION_PATTERNS]


def detect_injection(text: str) -> tuple[bool, list[str]]:
    """检测 Prompt 注入

    Args:
        text: 输入文本

    Returns:
        (是否检测到注入, 匹配的模式列表)
    """
    matched_patterns = []

    for pattern in COMPILED_PATTERNS:
        if pattern.search(text):
            matched_patterns.append(pattern.pattern)

    return len(matched_patterns) > 0, matched_patterns


def sanitize_input(text: str) -> str:
    """清理输入文本

    移除或转义可能的注入内容。

    Args:
        text: 输入文本

    Returns:
        清理后的文本
    """
    # 移除控制字符
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # 限制长度
    max_length = 5000
    if len(text) > max_length:
        text = text[:max_length]

    return text.strip()


def wrap_user_input(text: str) -> str:
    """包装用户输入

    使用分隔符明确标记用户输入，防止注入。

    Args:
        text: 用户输入

    Returns:
        包装后的文本
    """
    return f"<user_input>\n{text}\n</user_input>"
