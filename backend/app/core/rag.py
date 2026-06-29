"""RAG 知识库检索模块

三级检索策略：
1. Embedding 向量检索（语义相似）
2. Elasticsearch 全文检索（关键词精确 + 模糊）
3. 关键词匹配（兜底）
"""

import json
import logging
import re
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# 知识库目录
KNOWLEDGE_DIR = Path(__file__).parent.parent.parent / "knowledge"

# 全局知识库缓存
_knowledge_entries: list[dict] = []
_knowledge_loaded = False

# 向量索引缓存
_embeddings: list[list[float | None]] = None
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
            with open(json_file, encoding="utf-8") as f:
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

    # 自动索引到 Elasticsearch
    try:
        from app.core.es import index_entries
        from app.core.es import is_available as es_available
        if es_available() and entries:
            indexed = index_entries(entries)
            logger.info(f"ES 索引完成: {indexed}/{len(entries)} 条")
    except ImportError:
        pass

    return entries


def _get_embedding(text: str) -> list[float | None]:
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
    dot = sum(x * y for x, y in zip(a, b, strict=True))
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


def _rrf_fusion(result_lists: list[list[dict]], k: int = 60, top_k: int = 3) -> list[dict]:
    """Reciprocal Rank Fusion 融合多路检索结果

    公式：score = Σ 1/(k + rank_i)，rank_i 是该结果在第 i 路检索中的排名（从 1 开始）
    特点：只看排名不看绝对分数，量纲无关，适合异构检索器融合

    Args:
        result_lists: 多路检索结果列表，每路是 [{id, ...}, ...]
        k: RRF 参数，默认 60（论文经验值）
        top_k: 返回的结果数

    Returns:
        融合排序后的 top_k 结果
    """
    scores: dict[str, float] = {}
    entries: dict[str, dict] = {}

    for result_list in result_lists:
        for rank, entry in enumerate(result_list, 1):
            entry_id = entry.get("id") or entry.get("title", "")
            if not entry_id:
                continue
            scores[entry_id] = scores.get(entry_id, 0.0) + 1.0 / (k + rank)
            # 保留首次出现的完整 entry（同一条多路命中只存一份）
            if entry_id not in entries:
                entries[entry_id] = entry

    # 按融合分数排序
    sorted_ids = sorted(scores.keys(), key=lambda eid: scores[eid], reverse=True)
    return [entries[eid] for eid in sorted_ids[:top_k]]


def retrieve_context(query: str, top_k: int = 3) -> str:
    """三级混合检索：双路 RRF 融合 + 关键词兜底

    检索模式（由 RETRIEVAL_MODE 环境变量控制）：
    - fusion（默认）：向量 + ES 双路并行召回，RRF 融合排序；关键词仅在两路都挂了时兜底
    - cascade：串行降级（老逻辑），向量→ES→关键词，上一层有结果就跳过下一层
    - vector_only：仅向量检索

    Args:
        query: 查询文本（通常是存疑点的 source_text + reason）
        top_k: 返回结果数量

    Returns:
        格式化的上下文文本，可直接注入 LLM prompt
    """
    mode = settings.RETRIEVAL_MODE

    # ---------- fusion 模式：双路 RRF 融合 ----------
    if mode == "fusion":
        result_lists = []

        # 第 1 路：Embedding 向量检索
        if is_llm_available():
            vector_results = _vector_search(query, top_k * 2)
            if vector_results:
                result_lists.append(vector_results)

        # 第 2 路：ES 全文检索
        try:
            from app.core.es import is_available as es_available
            from app.core.es import search as es_search
            if es_available():
                es_results = es_search(query, top_k * 2)
                if es_results:
                    result_lists.append(es_results)
        except ImportError:
            pass

        # 融合：双路都有结果才融合，单路有结果直接用
        if len(result_lists) >= 2:
            results = _rrf_fusion(result_lists, k=settings.RRF_K, top_k=top_k)
        elif len(result_lists) == 1:
            results = result_lists[0][:top_k]
        else:
            # 双路都挂了 → 关键词兜底
            results = _keyword_search(query, top_k)

    # ---------- cascade 模式：串行降级（老逻辑）----------
    elif mode == "cascade":
        results = []

        if is_llm_available():
            results = _vector_search(query, top_k)

        if not results:
            try:
                from app.core.es import is_available as es_available
                from app.core.es import search as es_search
                if es_available():
                    results = es_search(query, top_k)
            except ImportError:
                pass

        if not results:
            results = _keyword_search(query, top_k)

    # ---------- vector_only 模式 ----------
    else:
        results = _vector_search(query, top_k) if is_llm_available() else []

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
