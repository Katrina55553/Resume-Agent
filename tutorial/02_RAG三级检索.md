# RAG 三级混合检索策略

## 技术原理

RAG（Retrieval Augmented Generation）= 检索增强生成。核心思路：

```
用户问题 → 检索知识库 → 把检索结果塞进 LLM prompt → LLM 生成更专业的回答
```

**为什么要 RAG？** LLM 的知识有截止日期，且可能幻觉。RAG 让 LLM 基于**你的知识库**回答，更准确、可溯源。

## 三级检索架构

```
查询: "MySQL 慢查询优化"
    │
    ├─→ 第 1 层: Embedding 向量检索（语义相似）
    │   "MySQL 查询太慢" → 匹配到 "慢查询优化"、"EXPLAIN 分析"
    │   原理: 文字 → 1536维向量 → 余弦相似度比较
    │
    ├─→ 第 2 层: Elasticsearch 全文检索（关键词精确+模糊）
    │   "MySQL" + "慢查询" → 匹配包含这些词的文档
    │   原理: 倒排索引 + TF-IDF 评分
    │
    └─→ 第 3 层: 关键词匹配（兜底）
        "MySQL" → 匹配标题含 MySQL 的条目
        原理: 简单字符串包含
```

## 为什么需要三层

| 场景 | Embedding | ES 全文 | 关键词 |
|------|-----------|---------|--------|
| "查询太慢" 想找 "慢查询优化" | ✅ 语义相似 | ❌ 词不一样 | ❌ 没命中 |
| "MySQL 索引" 想找 "MySQL 索引原理" | ✅ | ✅ 精确命中 | ✅ |
| "redis 缓存" 想找 "Redis 缓存穿透" | ✅ | ✅ 模糊匹配 | ✅ |
| "B+树" 想找 "索引数据结构" | ✅ 语义相关 | ❌ 词不同 | ❌ |

**单用任何一层都有盲区，三层互补覆盖所有场景。**

## 关键代码

### Embedding 向量检索

```python
# rag.py
def _vector_search(query: str, top_k: int = 3) -> list[dict]:
    query_emb = get_embedding(query)  # 文字 → 向量

    scored = []
    for i, emb in enumerate(embeddings):
        sim = cosine_similarity(query_emb, emb)  # 余弦相似度
        scored.append((sim, entries[i]))

    scored.sort(reverse=True)
    return [e for _, e in scored[:top_k]]
```

### Elasticsearch 全文检索

```python
# es.py
def search(query: str, top_k: int = 3) -> list[dict]:
    body = {
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["title^3", "content", "tags^2"],  # 标题权重3倍
                "type": "best_fields",
                "fuzziness": "AUTO",  # 模糊匹配
            }
        },
        "size": top_k,
    }
    result = es.search(index="interview_knowledge", body=body)
    return [hit["_source"] for hit in result["hits"]["hits"]]
```

### 三级检索串联

```python
# rag.py - retrieve_context
results = []

# 第 1 层: Embedding
if is_llm_available():
    results = _vector_search(query, top_k)

# 第 2 层: ES
if not results and es_available():
    results = es_search(query, top_k)

# 第 3 层: 关键词
if not results:
    results = _keyword_search(query, top_k)
```

## 知识库数据

```json
// knowledge/mysql.json
{
  "topic": "MySQL",
  "entries": [
    {
      "id": "mysql_001",
      "title": "B+树索引原理",
      "content": "InnoDB 使用 B+树作为索引结构...",
      "tags": ["索引", "B+树", "InnoDB"],
      "difficulty": "medium",
      "reference_answer": "B+树的特点：1）所有数据都在叶子节点..."
    }
  ]
}
```

5 个技术栈，32 条面试题：MySQL(8) + Redis(7) + Docker(5) + Python(6) + 系统设计(6)

## 面试高频问题

### Q1: Embedding 和全文检索的本质区别是什么？

**A:**
- **Embedding**：把文字变成高维向量（1536维），通过向量距离衡量**语义相似度**。"查询太慢"和"慢查询优化"词完全不同，但语义相近，向量距离近。
- **全文检索**：基于**词频统计**（TF-IDF），看的是关键词是否出现、出现频率。"MySQL 索引"和"MySQL 索引原理"词重叠多，得分高。

简单说：Embedding 理解**意思**，全文检索匹配**字面**。

### Q2: 为什么不用向量数据库（如 ChromaDB、Milvus）？

**A:** 数据量决定方案：
- **< 1000 条**：内存列表 + 余弦相似度就够了（当前方案）
- **1 万~100 万**：需要向量数据库（ChromaDB、Milvance）
- **> 100 万**：需要分布式向量数据库（Milvus、Pinecone）

项目只有 32 条面试题，用内存列表零依赖、零延迟。数据量增长后可以无缝切换到 ChromaDB。

### Q3: Elasticsearch 在这里的作用是什么？和 Redis 有什么区别？

**A:**
- **Elasticsearch**：全文搜索引擎，擅长**文本检索**（倒排索引、模糊匹配、分词）
- **Redis**：内存缓存/消息队列，擅长**键值存储**和**高速读写**

ES 不适合做缓存，Redis 不适合做全文检索。它们是互补关系：
- Redis：存 WebSocket 消息、Celery 任务、会话缓存
- ES：存知识库文档，提供全文检索

### Q4: 检索结果怎么注入 LLM prompt？

**A:** 检索到的文档格式化后拼接到 user_prompt 里：

```
参考知识（面试题库）：
[1] MySQL - B+树索引原理 (medium)
InnoDB 使用 B+树作为索引结构...
参考答案: B+树的特点：1）所有数据都在叶子节点...

[2] MySQL - 慢查询优化 (medium)
使用 EXPLAIN 分析执行计划...
参考答案: 优化步骤：1）开启 slow_query_log...

当前存疑点：
- 原文引用：优化了 MySQL 查询性能
- 追问轮次：第 1 轮

请生成下一个面试问题：
```

LLM 看到参考知识后，会生成更有针对性的问题。

### Q5: 如果知识库没有相关内容怎么办？

**A:** 三级检索都返回空时，`retrieve_context` 返回空字符串。LLM prompt 里就没有参考知识部分，LLM 会用自己的通用知识生成问题。不会报错，只是专业度稍低。
