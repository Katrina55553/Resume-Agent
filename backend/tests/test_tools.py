"""Tool Calling 工具模块测试

覆盖 3 个工具函数 + 工具调度器 execute_tool。
"""

from unittest.mock import patch

from app.core import tools

# ============================================================
# search_knowledge_base
# ============================================================


class TestSearchKnowledgeBase:
    """知识库检索工具"""

    def test_returns_retrieved_context(self):
        """retrieve_context 有结果时返回检索内容"""
        with patch.object(tools, "retrieve_context", return_value="MySQL 索引原理..."):
            result = tools.search_knowledge_base("MySQL 索引")
        assert "MySQL" in result

    def test_returns_fallback_when_no_result(self):
        """retrieve_context 返回空时给出兜底文案"""
        with patch.object(tools, "retrieve_context", return_value=""):
            result = tools.search_knowledge_base("不存在的关键词")
        assert result == "未找到相关知识库内容"

    def test_uses_extracted_keywords_when_available(self):
        """extract_technical_keywords 提取到关键词时用关键词检索"""
        with (
            patch.object(tools, "extract_technical_keywords", return_value=["MySQL", "Redis"]),
            patch.object(tools, "retrieve_context", return_value="ok") as mock_retrieve,
        ):
            tools.search_knowledge_base("聊聊 MySQL 和 Redis")
        # 检索时使用拼接后的关键词
        mock_retrieve.assert_called_once_with("MySQL Redis", top_k=3)

    def test_falls_back_to_raw_query_when_no_keywords(self):
        """extract_technical_keywords 返回空时使用原始 query"""
        with (
            patch.object(tools, "extract_technical_keywords", return_value=[]),
            patch.object(tools, "retrieve_context", return_value="ok") as mock_retrieve,
        ):
            tools.search_knowledge_base("聊聊你的项目")
        mock_retrieve.assert_called_once_with("聊聊你的项目", top_k=3)


# ============================================================
# lookup_resume_field
# ============================================================


class TestLookupResumeField:
    """简历字段查看工具"""

    def test_returns_unavailable_when_no_resume_data(self):
        assert tools.lookup_resume_field("skills") == "简历数据不可用"

    def test_returns_missing_when_field_not_present(self):
        result = tools.lookup_resume_field("skills", resume_data={"name": "张三"})
        assert "skills" in result

    def test_returns_empty_when_field_is_empty_list(self):
        result = tools.lookup_resume_field("projects", resume_data={"projects": []})
        assert "为空" in result

    def test_serializes_list_as_json(self):
        data = {"skills": ["Python", "FastAPI"]}
        result = tools.lookup_resume_field("skills", resume_data=data)
        assert "Python" in result
        assert "FastAPI" in result

    def test_returns_string_value_as_is(self):
        data = {"summary": "5年后端经验"}
        result = tools.lookup_resume_field("summary", resume_data=data)
        assert result == "5年后端经验"


# ============================================================
# verify_code_snippet
# ============================================================


class TestVerifyCodeSnippet:
    """代码片段验证工具"""

    def test_returns_llm_analysis(self):
        # verify_code_snippet 内部延迟导入 call_llm，需 patch 源模块
        with patch("app.core.llm.call_llm", return_value="代码逻辑正确") as mock_llm:
            result = tools.verify_code_snippet("print('hello')", "Python")
        assert result == "代码逻辑正确"
        # 验证 prompt 包含代码和语言
        call_args = mock_llm.call_args
        assert "Python" in call_args.kwargs["user_prompt"]
        assert "print('hello')" in call_args.kwargs["user_prompt"]

    def test_includes_context_in_prompt_when_provided(self):
        with patch("app.core.llm.call_llm", return_value="ok") as mock_llm:
            tools.verify_code_snippet("SELECT *", "SQL", context="用户登录查询")
        call_args = mock_llm.call_args
        assert "用户登录查询" in call_args.kwargs["user_prompt"]

    def test_returns_fallback_when_llm_unavailable(self):
        with patch("app.core.llm.call_llm", return_value=None):
            result = tools.verify_code_snippet("x = 1", "Python")
        assert result == "无法分析代码片段"


# ============================================================
# execute_tool
# ============================================================


class TestExecuteTool:
    """工具调度器"""

    def test_dispatches_to_search_knowledge_base(self):
        with patch.object(tools, "search_knowledge_base", return_value="检索结果") as mock_search:
            result = tools.execute_tool(
                "search_knowledge_base",
                {"query": "Redis 缓存"},
            )
        assert result == "检索结果"
        mock_search.assert_called_once_with(query="Redis 缓存")

    def test_dispatches_to_lookup_resume_field_with_resume_data(self):
        resume_data = {"skills": ["Python"]}
        with patch.object(tools, "lookup_resume_field", return_value="Python") as mock_lookup:
            result = tools.execute_tool(
                "lookup_resume_field",
                {"field": "skills"},
                resume_data=resume_data,
            )
        assert result == "Python"
        mock_lookup.assert_called_once_with(field="skills", resume_data=resume_data)

    def test_dispatches_to_verify_code_snippet(self):
        with patch.object(tools, "verify_code_snippet", return_value="ok") as mock_verify:
            result = tools.execute_tool(
                "verify_code_snippet",
                {"code": "x=1", "language": "Python", "context": "demo"},
            )
        assert result == "ok"
        mock_verify.assert_called_once_with(code="x=1", language="Python", context="demo")

    def test_returns_unknown_tool_message(self):
        result = tools.execute_tool("nonexistent_tool", {})
        assert "未知工具" in result
        assert "nonexistent_tool" in result

    def test_catches_exception_and_returns_error_message(self):
        """工具执行抛异常时返回错误信息而非崩溃"""
        with patch.object(tools, "search_knowledge_base", side_effect=RuntimeError("boom")):
            result = tools.execute_tool("search_knowledge_base", {"query": "x"})
        assert "工具执行失败" in result
        assert "boom" in result

    def test_resume_data_not_injected_when_none(self):
        """resume_data 为 None 时不修改 tool_args"""
        with patch.object(tools, "search_knowledge_base", return_value="ok"):
            args = {"query": "test"}
            tools.execute_tool("search_knowledge_base", args, resume_data=None)
        # 原始 args 不应被污染
        assert "_resume_data" not in args


# ============================================================
# get_tools
# ============================================================


class TestGetTools:
    """工具定义"""

    def test_returns_three_tools(self):
        tool_list = tools.get_tools()
        assert len(tool_list) == 3

    def test_tool_names_match_registry(self):
        names = {t["function"]["name"] for t in tools.get_tools()}
        assert names == {
            "search_knowledge_base",
            "lookup_resume_field",
            "verify_code_snippet",
        }

    def test_each_tool_has_required_schema_fields(self):
        for tool in tools.get_tools():
            assert tool["type"] == "function"
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            assert func["parameters"]["type"] == "object"
