"""Elasticsearch 全文检索模块

提供知识库的全文检索能力，与 Embedding 向量检索互补。
- Embedding: 语义相似（"查询太慢" 匹配 "慢查询优化"）
- ES 全文: 关键词精确（"MySQL 索引" 匹配包含这两个词的文档）
"""

import logging

from elasticsearch import Elasticsearch

from app.core.config import settings

logger = logging.getLogger(__name__)

_es_client: Elasticsearch | None = None

INDEX_NAME = "interview_knowledge"


def _get_es() -> Elasticsearch | None:
    """获取 ES 客户端（懒加载）"""
    global _es_client
    if _es_client is None:
        try:
            _es_client = Elasticsearch(settings.ELASTICSEARCH_URL)
            if not _es_client.ping():
                logger.warning("Elasticsearch 连接失败")
                _es_client = None
                return None
        except Exception as e:
            logger.warning(f"Elasticsearch 初始化失败: {e}")
            return None
    return _es_client


def create_index() -> bool:
    """创建知识库索引（如果不存在）"""
    es = _get_es()
    if es is None:
        return False

    if es.indices.exists(index=INDEX_NAME):
        return True

    mapping = {
        "mappings": {
            "properties": {
                "entry_id": {"type": "keyword"},
                "topic": {"type": "keyword"},
                "title": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_smart"},
                "content": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_smart"},
                "tags": {"type": "keyword"},
                "difficulty": {"type": "keyword"},
                "reference_answer": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_smart"},
            }
        }
    }

    try:
        es.indices.create(index=INDEX_NAME, body=mapping)
        logger.info(f"ES 索引 {INDEX_NAME} 创建成功")
        return True
    except Exception as e:
        logger.error(f"ES 索引创建失败: {e}")
        return False


def index_entries(entries: list[dict]) -> int:
    """批量索引知识库条目

    Args:
        entries: 知识库条目列表，每条需包含 id, topic, title, content, tags 等字段

    Returns:
        成功索引的条目数
    """
    es = _get_es()
    if es is None:
        return 0

    create_index()

    from elasticsearch.helpers import bulk

    actions = []
    for entry in entries:
        actions.append({
            "_index": INDEX_NAME,
            "_id": entry.get("id", ""),
            "_source": {
                "entry_id": entry.get("id", ""),
                "topic": entry.get("topic", ""),
                "title": entry.get("title", ""),
                "content": entry.get("content", ""),
                "tags": entry.get("tags", []),
                "difficulty": entry.get("difficulty", ""),
                "reference_answer": entry.get("reference_answer", ""),
            },
        })

    try:
        success, _ = bulk(es, actions, raise_on_error=False)
        es.indices.refresh(index=INDEX_NAME)
        logger.info(f"ES 索引 {success} 条文档")
        return success
    except Exception as e:
        logger.error(f"ES 批量索引失败: {e}")
        return 0


def search(query: str, top_k: int = 3) -> list[dict]:
    """全文检索知识库

    Args:
        query: 检索关键词
        top_k: 返回结果数

    Returns:
        匹配的文档列表 [{title, content, topic, ...}, ...]
    """
    es = _get_es()
    if es is None:
        return []

    try:
        body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "content", "tags^2", "reference_answer"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            },
            "size": top_k,
        }

        result = es.search(index=INDEX_NAME, body=body)
        hits = result.get("hits", {}).get("hits", [])

        return [
            {
                "id": hit["_source"].get("entry_id", ""),
                "topic": hit["_source"].get("topic", ""),
                "title": hit["_source"].get("title", ""),
                "content": hit["_source"].get("content", ""),
                "tags": hit["_source"].get("tags", []),
                "difficulty": hit["_source"].get("difficulty", ""),
                "reference_answer": hit["_source"].get("reference_answer", ""),
                "score": hit.get("_score", 0),
            }
            for hit in hits
        ]
    except Exception as e:
        logger.error(f"ES 检索失败: {e}")
        return []


def is_available() -> bool:
    """检查 ES 是否可用"""
    return _get_es() is not None
