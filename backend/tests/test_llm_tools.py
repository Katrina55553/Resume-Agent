"""LLM tool-calling compatibility tests."""

from app.core.llm import _parse_tool_calls_from_text, _strip_dsml_tool_text


def test_malformed_dsml_tool_call_without_arguments_is_ignored():
    content = """
简历信息，我看到候选人提到了两个具体项目，但并未列出10个产品。现在我需要针对这个存疑点进行提问。

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="search_knowledge_base">
<｜｜DSML｜｜invoke name="search_knowledge_base">
</｜｜DSML｜｜invoke>
</｜｜DSML｜｜tool_calls>
"""

    assert _parse_tool_calls_from_text(content) == []


def test_dsml_tool_text_is_not_displayable_content():
    content = """
简历信息，我看到候选人提到了两个具体项目，但并未列出10个产品。现在我需要针对这个存疑点进行提问。

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="search_knowledge_base">
</｜｜DSML｜｜tool_calls>
"""

    assert _strip_dsml_tool_text(content) == ""


def test_dsml_tool_call_with_arguments_is_parsed():
    content = """
<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="search_knowledge_base">
{"query": "FastAPI WebSocket 面试问题"}
</｜｜DSML｜｜invoke>
</｜｜DSML｜｜tool_calls>
"""

    assert _parse_tool_calls_from_text(content) == [
        {
            "id": "call_0",
            "name": "search_knowledge_base",
            "arguments": {"query": "FastAPI WebSocket 面试问题"},
        },
    ]
