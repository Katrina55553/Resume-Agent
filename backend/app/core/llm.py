"""LLM 调用模块

提供统一的 LLM 调用接口，使用 OpenAI 兼容格式（支持 DeepSeek 等第三方）。
所有节点共用此模块，避免重复初始化客户端。
"""

import json
import logging
import re
from typing import Optional

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Optional[OpenAI] = None


def _get_client() -> Optional[OpenAI]:
    """懒加载 OpenAI 客户端"""
    global _client
    if _client is None:
        if not settings.LLM_API_KEY:
            return None
        _client = OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )
    return _client


def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> Optional[str]:
    """调用 LLM，返回文本响应。

    Returns:
        LLM 响应文本，失败时返回 None。
    """
    client = _get_client()
    if client is None:
        logger.warning("LLM API key 未配置，跳过 LLM 调用")
        return None

    try:
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        return None


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> Optional[dict]:
    """调用 LLM 并解析 JSON 响应。

    自动处理 ```json ... ``` 包裹。

    Returns:
        解析后的 dict，失败时返回 None。
    """
    text = call_llm(system_prompt, user_prompt, temperature, max_tokens)
    if text is None:
        return None

    # 提取 JSON
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            logger.error(f"LLM 返回的 JSON 解析失败: {text[:200]}")
            return None

    # 尝试直接解析（可能没有包裹）
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error(f"LLM 返回内容不是有效 JSON: {text[:200]}")
        return None


def is_llm_available() -> bool:
    """检查 LLM 是否可用"""
    return bool(settings.LLM_API_KEY)
