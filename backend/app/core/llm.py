"""LLM 调用模块

提供统一的 LLM 调用接口，使用 OpenAI 兼容格式（支持 DeepSeek 等第三方）。
所有节点共用此模块，避免重复初始化客户端。
支持 Tool Calling（Function Calling）。
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

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


def _parse_tool_calls_from_text(content: str) -> List[Dict[str, Any]]:
    """从文本内容中解析工具调用（兼容 DeepSeek 等不支持结构化 tool_calls 的模型）。

    DeepSeek 可能把工具调用输出为文本：
    <｜tool_calls｜><｜tool_call｜>func_name({"arg": "val"})<｜/tool_call｜><｜/tool_calls｜>
    或普通格式：
    <tool_call>func_name({"arg": "val"})</tool_call>
    """
    tool_calls = []

    # 尝试多种格式
    patterns = [
        # DeepSeek 格式：<｜tool_call｜>name({...})<｜/tool_call｜>
        r'<｜tool_call｜>(\w+)\((\{.*?\})\)<｜/tool_call｜>',
        # 通用 XML 格式：<tool_call>name({...})</tool_call>
        r'<tool_call>(\w+)\((\{.*?\})\)</tool_call>',
        # 简单格式：name({"arg": "val"})
        r'(search_knowledge_base|lookup_resume_field|verify_code_snippet)\((\{[^)]+\})\)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, content, re.DOTALL)
        if matches:
            for i, (func_name, args_str) in enumerate(matches):
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({
                    "id": f"call_{i}",
                    "name": func_name,
                    "arguments": args,
                })
            break

    return tool_calls


def call_llm_with_tools(
    system_prompt: str,
    user_prompt: str,
    tools: List[dict],
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """调用 LLM 并支持 Tool Calling。

    先尝试结构化 tool_calls（OpenAI 格式），
    如果模型不支持则从文本内容中解析工具调用（DeepSeek 兼容）。

    Returns:
        (content, tool_calls) 元组：
        - content: LLM 的文本回复（如果有）
        - tool_calls: 工具调用列表 [{"id": ..., "name": ..., "arguments": {...}}, ...]
        - 如果调用失败返回 (None, [])
    """
    client = _get_client()
    if client is None:
        logger.warning("LLM API key 未配置，跳过 LLM 调用")
        return None, []

    try:
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=tools,
            tool_choice="auto",
        )

        message = response.choices[0].message
        content = message.content or ""

        # 优先：结构化 tool_calls（OpenAI 原生格式）
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args,
                })

        # 降级：从文本内容中解析工具调用（DeepSeek 兼容）
        if not tool_calls and content:
            tool_calls = _parse_tool_calls_from_text(content)
            if tool_calls:
                # 去掉内容中的工具调用标记，保留纯文本
                for pattern in [
                    r'<｜tool_calls｜>.*?<｜/tool_calls｜>',
                    r'<tool_call>.*?</tool_call>',
                ]:
                    content = re.sub(pattern, '', content, flags=re.DOTALL).strip()

        return content.strip() if content else "", tool_calls

    except Exception as e:
        logger.error(f"LLM Tool Calling 调用失败: {e}")
        return None, []


def continue_with_tool_results(
    system_prompt: str,
    messages: List[dict],
    tool_results: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> Optional[str]:
    """将工具执行结果返回给 LLM，获取最终回复。

    Args:
        system_prompt: 系统提示
        messages: 完整对话历史（包含 assistant 的 tool_calls 消息）
        tool_results: 工具执行结果 [{"tool_call_id": ..., "content": ...}]
        temperature: 温度
        max_tokens: 最大 token

    Returns:
        LLM 最终文本回复
    """
    client = _get_client()
    if client is None:
        return None

    try:
        # 构建消息：system + 历史 + tool results
        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages)
        for tr in tool_results:
            full_messages.append({
                "role": "tool",
                "tool_call_id": tr["tool_call_id"],
                "content": tr["content"],
            })

        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=full_messages,
        )

        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM Tool 结果处理失败: {e}")
        return None
