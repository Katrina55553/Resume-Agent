"""RAG 知识库检索模块

从 knowledge/ 目录加载面试题知识库，提供向量检索和关键词检索两种模式。
LLM 可用时用 embedding 向量检索，否则降级到关键词匹配。
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# 知识库目录
KNOWLEDGE_DIR = Path(__file__).parent.parent.parent / "knowledge"

# 全局知识库缓存
_knowledge_entries: list[dict] = []
_knowledge_loaded = False

# 向量索引缓存
_embeddings: Optional[list[list[float]]] = None
_embedding_entries: list[dict] = []


def _load_knowledge_base() -> list[dict]:
    """加载 knowledge/ 目录下所有 JSON 文件"""
    global _knowledge_entries, _knowledge_loaded

    if _knowledge_loaded:
        return _knowledge_entries

    entries = []
    if not KNOWLEDGE_DIR.exists():
        logger.warning(f"知识库目录不存在: {KNOWLEDGE_DIR}")
        _knowledge_loaded = True
        return entries

    for json_file in KNOWLEDGE_DIR.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            topic = data.get("topic", json_file.stem)
            for entry in data.get("entries", []):
                entry["topic"] = topic
                entries.append(entry)
            logger.info(f"加载知识库: {topic} ({len(data.get('entries', []))} 条)")
        except Exception as e:
            logger.error(f"加载知识库文件失败 {json_file}: {e}")

    _knowledge_entries = entries
    _knowledge_loaded = True
    logger.info(f"知识库加载完成，共 {len(entries)} 条")
    return entries


def _get_embedding(text: str) -> Optional[list[float]]:
    """获取文本的 embedding 向量"""
    from app.core.llm import _get_client

    client = _get_client()
    if client is None:
        return None

    try:
        response = client.embeddings.create(
            model="deepseek-embedding",
            input=text,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.warning(f"Embedding 调用失败: {e}")
        return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算余弦相似度"""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _build_embedding_index():
    """构建 embedding 向量索引"""
    global _embeddings, _embedding_entries

    entries = _load_knowledge_base()
    if not entries:
        return

    # 构建每条知识的文本表示
    texts = []
    for entry in entries:
        text = (
            f"{entry.get('title', '')} "
            f"{entry.get('content', '')} "
            f"{' '.join(entry.get('tags', []))}"
        )
        texts.append(text)

    # 批量获取 embedding
    embeddings = []
    valid_entries = []
    for i, text in enumerate(texts):
        emb = _get_embedding(text)
        if emb:
            embeddings.append(emb)
            valid_entries.append(entries[i])

    if embeddings:
        _embeddings = embeddings
        _embedding_entries = valid_entries
        logger.info(f"向量索引构建完成，共 {len(embeddings)} 条")


def _vector_search(query: str, top_k: int = 3) -> list[dict]:
    """向量检索"""
    global _embeddings, _embedding_entries

    # 懒加载索引
    if _embeddings is None:
        _build_embedding_index()

    if not _embeddings:
        return []

    query_emb = _get_embedding(query)
    if not query_emb:
        return []

    # 计算相似度
    scored = []
    for i, emb in enumerate(_embeddings):
        sim = _cosine_similarity(query_emb, emb)
        scored.append((sim, _embedding_entries[i]))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:top_k]]


def _keyword_search(query: str, top_k: int = 3) -> list[dict]:
    """关键词匹配检索（降级方案）"""
    entries = _load_knowledge_base()
    if not entries:
        return []

    # 从查询中提取关键词
    keywords = set()
    for word in re.findall(r"[一-鿿]{2,}", query):
        keywords.add(word.lower())
    for word in re.findall(r"[a-zA-Z][a-zA-Z0-9.+#]{1,}", query):
        keywords.add(word.lower())

    if not keywords:
        return []

    # 打分
    scored = []
    for entry in entries:
        score = 0
        text = (
            f"{entry.get('title', '')} {entry.get('content', '')} "
            f"{' '.join(entry.get('tags', []))} {entry.get('topic', '')}"
        ).lower()

        for kw in keywords:
            if kw in text:
                score += 1
            if kw in entry.get("title", "").lower():
                score += 2
            if kw in [t.lower() for t in entry.get("tags", [])]:
                score += 1.5

        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:top_k]]


def retrieve_context(query: str, top_k: int = 3) -> str:
    """从知识库检索与查询相关的上下文

    Args:
        query: 查询文本（通常是存疑点的 source_text + reason）
        top_k: 返回结果数量

    Returns:
        格式化的上下文文本，可直接注入 LLM prompt
    """
    results = []

    # 优先用向量检索
    if is_llm_available():
        results = _vector_search(query, top_k)

    # 向量检索无结果时降级到关键词
    if not results:
        results = _keyword_search(query, top_k)

    if not results:
        return ""

    # 格式化
    context_parts = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        topic = r.get("topic", "")
        content = r.get("content", "")
        ref = r.get("reference_answer", "")
        difficulty = r.get("difficulty", "")

        part = f"[{i}] {topic} - {title}"
        if difficulty:
            part += f" ({difficulty})"
        part += f"\n{content}"
        if ref:
            part += f"\n参考答案: {ref}"
        context_parts.append(part)

    return "\n\n".join(context_parts)


def extract_technical_keywords(text: str) -> list[str]:
    """从文本中提取技术关键词"""
    tech_keywords = [
        "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
        "Python", "Java", "Go", "JavaScript", "TypeScript", "C++", "Rust",
        "React", "Vue", "Angular", "Node.js", "Django", "Flask", "FastAPI", "Spring",
        "Docker", "Kubernetes", "K8s", "AWS", "Linux", "Git", "Nginx",
        "Kafka", "RabbitMQ", "GraphQL", "gRPC", "WebSocket",
        "微服务", "分布式", "缓存", "消息队列", "负载均衡",
        "索引", "事务", "锁", "分库分表", "主从复制",
        "B+树", "MVCC", "SQL优化", "慢查询",
    ]

    found = []
    text_lower = text.lower()
    for kw in tech_keywords:
        if kw.lower() in text_lower:
            found.append(kw)

    return list(set(found))


def is_llm_available() -> bool:
    """检查 LLM 是否可用（用于判断是否可以用 embedding）"""
    return bool(settings.LLM_API_KEY)
