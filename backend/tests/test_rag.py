"""RAG 知识库检索模块测试

覆盖：关键词提取、余弦相似度、关键词检索、retrieve_context 三级降级、extract_technical_keywords。
"""


import pytest

from app.core import rag

# ============================================================
# extract_technical_keywords
# ============================================================


class TestExtractTechnicalKeywords:
    """技术关键词提取"""

    def test_extracts_known_keywords(self):
        result = rag.extract_technical_keywords("我熟悉 MySQL 和 Redis 缓存")
        assert "MySQL" in result
        assert "Redis" in result
        assert "缓存" in result

    def test_case_insensitive_match(self):
        """关键词大小写不敏感，但返回原始大小写"""
        result = rag.extract_technical_keywords("我用过 python 和 docker")
        assert "Python" in result
        assert "Docker" in result

    def test_returns_empty_for_no_match(self):
        result = rag.extract_technical_keywords("今天天气不错")
        assert result == []

    def test_deduplicates_keywords(self):
        """同一关键词多次出现只返回一次"""
        result = rag.extract_technical_keywords("MySQL MySQL MySQL")
        assert result.count("MySQL") == 1

    def test_empty_text(self):
        assert rag.extract_technical_keywords("") == []


# ============================================================
# _cosine_similarity
# ============================================================


class TestCosineSimilarity:
    """余弦相似度"""

    def test_identical_vectors(self):
        assert rag._cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        """正交向量相似度为 0"""
        assert rag._cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_zero_vector_returns_zero(self):
        """零向量返回 0，避免除零"""
        assert rag._cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
        assert rag._cosine_similarity([1.0, 2.0], [0.0, 0.0]) == 0.0

    def test_opposite_vectors(self):
        """方向相反的向量相似度为 -1"""
        assert rag._cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_different_magnitude_same_direction(self):
        """同方向不同模长相似度仍为 1"""
        assert rag._cosine_similarity([1.0, 1.0], [2.0, 2.0]) == pytest.approx(1.0)


# ============================================================
# _keyword_search
# ============================================================


class TestKeywordSearch:
    """关键词检索（降级方案）"""

    def test_returns_empty_when_no_entries(self, monkeypatch):
        """知识库为空时返回空列表"""
        monkeypatch.setattr(rag, "_load_knowledge_base", lambda: [])
        assert rag._keyword_search("MySQL") == []

    def test_matches_by_chinese_keyword(self, monkeypatch):
        entries = [
            {
                "title": "MySQL 索引原理",
                "content": "B+树索引结构",
                "tags": ["MySQL", "索引"],
                "topic": "数据库",
            },
            {
                "title": "Redis 缓存",
                "content": "缓存穿透解决方案",
                "tags": ["Redis"],
                "topic": "缓存",
            },
        ]
        monkeypatch.setattr(rag, "_load_knowledge_base", lambda: entries)
        results = rag._keyword_search("MySQL 索引")
        assert len(results) >= 1
        assert results[0]["title"] == "MySQL 索引原理"

    def test_matches_by_english_keyword(self, monkeypatch):
        entries = [
            {
                "title": "Docker 入门",
                "content": "容器化部署",
                "tags": ["Docker"],
                "topic": "运维",
            },
        ]
        monkeypatch.setattr(rag, "_load_knowledge_base", lambda: entries)
        results = rag._keyword_search("Docker")
        assert len(results) == 1

    def test_returns_empty_when_no_keyword_match(self, monkeypatch):
        entries = [{"title": "MySQL", "content": "数据库", "tags": [], "topic": "DB"}]
        monkeypatch.setattr(rag, "_load_knowledge_base", lambda: entries)
        results = rag._keyword_search("Kubernetes")
        assert results == []

    def test_returns_empty_when_query_has_no_extractable_keyword(self, monkeypatch):
        """查询中没有可提取的关键词时返回空"""
        entries = [{"title": "test", "content": "x", "tags": [], "topic": "t"}]
        monkeypatch.setattr(rag, "_load_knowledge_base", lambda: entries)
        results = rag._keyword_search("   ")
        assert results == []

    def test_top_k_limit(self, monkeypatch):
        """top_k 限制返回数量"""
        entries = [
            {"title": f"item-{i}", "content": "MySQL", "tags": [], "topic": "DB"}
            for i in range(10)
        ]
        monkeypatch.setattr(rag, "_load_knowledge_base", lambda: entries)
        results = rag._keyword_search("MySQL", top_k=3)
        assert len(results) == 3

    def test_title_match_scores_higher(self, monkeypatch):
        """标题命中得分应高于内容命中"""
        entries = [
            {"title": "其他主题", "content": "MySQL 内容", "tags": [], "topic": "x"},
            {"title": "MySQL 主题", "content": "其他内容", "tags": [], "topic": "y"},
        ]
        monkeypatch.setattr(rag, "_load_knowledge_base", lambda: entries)
        results = rag._keyword_search("MySQL")
        # 标题命中的应排在前面
        assert results[0]["title"] == "MySQL 主题"


# ============================================================
# retrieve_context
# ============================================================


class TestRetrieveContext:
    """三级检索集成"""

    def test_returns_empty_when_all_layers_fail(self, monkeypatch):
        """三层都失败时返回空字符串"""
        monkeypatch.setattr(rag, "is_llm_available", lambda: False)
        monkeypatch.setattr(rag, "_keyword_search", lambda q, top_k=3: [])
        # ES 模块不存在，会触发 ImportError
        assert rag.retrieve_context("anything") == ""

    def test_falls_back_to_keyword_search(self, monkeypatch):
        """LLM 不可用时降级到关键词检索"""
        monkeypatch.setattr(rag, "is_llm_available", lambda: False)
        monkeypatch.setattr(
            rag,
            "_keyword_search",
            lambda q, top_k=3: [
                {
                    "title": "MySQL 索引",
                    "content": "B+树",
                    "tags": [],
                    "topic": "DB",
                    "reference_answer": "使用 B+树",
                    "difficulty": "中等",
                },
            ],
        )
        result = rag.retrieve_context("MySQL")
        assert "MySQL 索引" in result
        assert "B+树" in result
        assert "参考答案" in result
        assert "中等" in result

    def test_format_includes_all_fields(self, monkeypatch):
        """格式化输出包含 topic/title/content/reference_answer/difficulty"""
        monkeypatch.setattr(rag, "is_llm_available", lambda: False)
        monkeypatch.setattr(
            rag,
            "_keyword_search",
            lambda q, top_k=3: [
                {
                    "title": "T1",
                    "content": "C1",
                    "tags": [],
                    "topic": "Topic1",
                    "reference_answer": "RA1",
                    "difficulty": "困难",
                },
            ],
        )
        result = rag.retrieve_context("query")
        assert "Topic1" in result
        assert "T1" in result
        assert "C1" in result
        assert "RA1" in result
        assert "困难" in result

    def test_skips_empty_optional_fields(self, monkeypatch):
        """reference_answer/difficulty 为空时不输出该行"""
        monkeypatch.setattr(rag, "is_llm_available", lambda: False)
        monkeypatch.setattr(
            rag,
            "_keyword_search",
            lambda q, top_k=3: [
                {"title": "T", "content": "C", "tags": [], "topic": "Topic"},
            ],
        )
        result = rag.retrieve_context("query")
        assert "参考答案" not in result


# ============================================================
# _load_knowledge_base
# ============================================================


class TestLoadKnowledgeBase:
    """知识库加载"""

    def test_returns_cached_entries_on_second_call(self, monkeypatch):
        """第二次调用应返回缓存，不再读磁盘"""
        # 重置缓存
        rag._knowledge_entries = []
        rag._knowledge_loaded = False

        # 模拟目录存在但 glob 返回空（无 JSON 文件）
        import pathlib

        import app.core.rag as rag_module
        fake_dir = pathlib.Path("/fake/knowledge")
        monkeypatch.setattr(rag_module, "KNOWLEDGE_DIR", fake_dir)
        monkeypatch.setattr(pathlib.Path, "exists", lambda self: True)
        monkeypatch.setattr(pathlib.Path, "glob", lambda self, pattern: [])

        first = rag._load_knowledge_base()
        second = rag._load_knowledge_base()

        # 两次返回同一对象（缓存生效）
        assert first is second

    def test_returns_empty_when_dir_not_exist(self, monkeypatch):
        """目录不存在时返回空列表"""
        import pathlib

        rag._knowledge_entries = []
        rag._knowledge_loaded = False

        monkeypatch.setattr(pathlib.Path, "exists", lambda self: False)
        result = rag._load_knowledge_base()
        assert result == []


# ============================================================
# is_llm_available
# ============================================================


class TestIsLlmAvailable:
    """LLM 可用性检查"""

    def test_returns_true_when_api_key_set(self, monkeypatch):
        monkeypatch.setattr(rag.settings, "LLM_API_KEY", "sk-test")
        assert rag.is_llm_available() is True

    def test_returns_false_when_api_key_empty(self, monkeypatch):
        monkeypatch.setattr(rag.settings, "LLM_API_KEY", "")
        assert rag.is_llm_available() is False
