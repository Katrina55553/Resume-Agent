"""LLM tool-calling compatibility tests."""

from types import SimpleNamespace

from app.core import llm
from app.core.llm import _parse_tool_calls_from_text, _strip_dsml_tool_text, call_llm_stream


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


def test_stream_drops_entire_output_when_dsml_is_split_across_chunks(monkeypatch):
    chunks = [
        "简历信息，我看到候选人提到了两个具体项目，",
        "但并未列出10个产品。",
        "<｜｜DSML｜｜tool_calls>",
        "<｜｜DSML｜｜invoke name=\"search_knowledge_base\">",
        "<｜｜DSML｜｜invoke name=\"search_knowledge_base\">",
        "<｜｜DSML｜｜invoke name=\"search_knowledge_base\">",
        "</｜｜DSML｜｜invoke>",
        "</｜｜DSML｜｜invoke>",
        "</｜｜DSML｜｜invoke>",
        "</｜｜DSML｜｜tool_calls>",
    ]

    class FakeCompletions:
        def create(self, **kwargs):
            assert kwargs["stream"] is True
            return [
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=chunk))],
                )
                for chunk in chunks
            ]

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions()),
    )
    monkeypatch.setattr(llm, "_get_client", lambda: fake_client)

    assert list(call_llm_stream("system", "user")) == []


def test_stream_yields_plain_question(monkeypatch):
    chunks = ["能介绍一下", "这个项目里你的具体职责吗？"]

    class FakeCompletions:
        def create(self, **kwargs):
            assert kwargs["stream"] is True
            return [
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=chunk))],
                )
                for chunk in chunks
            ]

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions()),
    )
    monkeypatch.setattr(llm, "_get_client", lambda: fake_client)

    assert list(call_llm_stream("system", "user")) == chunks
