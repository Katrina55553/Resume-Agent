# WebSocket 流式通信 + 断线恢复

## 技术原理

### WebSocket vs HTTP 轮询

```
HTTP 轮询（旧方案）：
前端: 有新消息吗？→ 后端: 没有
前端: 有新消息吗？→ 后端: 没有
前端: 有新消息吗？→ 后端: 有！（问题内容）
// 每次都建 TCP 连接，浪费资源

WebSocket（新方案）：
前端: 建立连接 ──────────────────── 持续保持
后端: → 问题内容（即时推送）
后端: → 状态更新（即时推送）
// 一次握手，长连接，服务端主动推送
```

### 流式推送（逐字输出）

```
LLM 生成: "你简历中提到使用 MySQL，能详细说说吗？"

传统方式: 等 LLM 全部生成完 → 一次性发给前端 → 用户等 3 秒

流式方式: LLM 每生成一个 token → 立刻推给前端
  → "你"
  → "简历"
  → "中"
  → "提到"
  → "使用"
  → " MySQL"
  → ...
// 用户看到文字逐渐出现，首字延迟 200ms
```

## 消息协议

```
客户端 → 服务端:
  {"type": "answer", "content": "我的回答..."}
  {"type": "skip"}
  {"type": "start"}

服务端 → 客户端:
  {"type": "question_start", "point_id": "...", "round": 1}  ← 开始生成
  {"type": "chunk", "content": "你"}                          ← 逐字推送
  {"type": "chunk", "content": "简历"}
  {"type": "chunk", "content": "中"}
  ...
  {"type": "question", "content": "完整问题", "point_id": "..."}  ← 确认
  {"type": "status", "point_states": {...}, "progress": 0.5}     ← 状态
  {"type": "complete", "report": {...}}                          ← 面试结束
```

## 断线恢复三层机制

### 第 1 层：前端消息队列

```typescript
// interviewStore.ts
let messageQueue: string[] = [];

sendAnswer: (content) => {
    const payload = JSON.stringify({ type: "answer", content });
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(payload);
    } else {
        messageQueue.push(payload);  // 断线时缓存
    }
}

// 重连后自动发送
socket.onopen = () => {
    while (messageQueue.length > 0) {
        socket.send(messageQueue.shift());
    }
}
```

### 第 2 层：Redis 消息缓存

```python
# msg_cache.py
async def push_message(session_id, msg_type, data):
    """后端生成消息时，先写 Redis 再发 WebSocket"""
    entry = json.dumps({"type": msg_type, "data": data})
    await redis.rpush(f"ws:msgs:{session_id}", entry)
    await redis.expire(f"ws:msgs:{session_id}", 3600)

async def get_pending_messages(session_id):
    """客户端重连时，取出未消费的消息"""
    script = """
    local msgs = redis.call('LRANGE', KEYS[1], 0, -1)
    redis.call('DEL', KEYS[1])
    return msgs
    """
    return await redis.eval(script, 1, f"ws:msgs:{session_id}")
```

### 第 3 层：数据库持久化

```python
# 每条消息都存 interview_messages 表
await _save_message(session_id, "assistant", question_text, point_id)

# 页面刷新时从 DB 恢复完整历史
async def resume_interview(session_id):
    messages = await db.execute(
        select(InterviewMessageORM).where(...)
    )
    return messages
```

## 断线重连（指数退避）

```typescript
// interviewStore.ts
const MAX_RETRIES = 5;

socket.onclose = (event) => {
    if (!isComplete && event.code !== 1000) {
        if (retryCount < MAX_RETRIES) {
            const delay = Math.min(1000 * Math.pow(2, retryCount), 16000);
            retryCount++;
            // 1s → 2s → 4s → 8s → 16s
            setTimeout(connect, delay);
        }
    }
}
```

## 流式推送实现

```python
# ws.py - 用 asyncio.Queue 跨线程推送
chunk_queue = asyncio.Queue()

def _stream_to_queue():
    """后台线程运行 LLM 流式生成"""
    for chunk in generate_question_stream(point, messages, round):
        loop.call_soon_threadsafe(chunk_queue.put_nowait, chunk)
    loop.call_soon_threadsafe(chunk_queue.put_nowait, None)

threading.Thread(target=_stream_to_queue, daemon=True).start()

# 主循环逐 chunk 推送
while True:
    chunk = await chunk_queue.get()
    if chunk is None:
        break
    await websocket.send_json({"type": "chunk", "content": chunk})
```

## 面试高频问题

### Q1: WebSocket 和 SSE 的区别？为什么选 WebSocket？

**A:**
| | WebSocket | SSE |
|--|-----------|-----|
| 方向 | 双向 | 单向（服务端→客户端） |
| 协议 | ws:// | HTTP text/event-stream |
| 复用 | 一个连接搞定 | 需要额外连接发答案 |

面试场景需要**双向通信**（发答案 + 收问题），WebSocket 一个连接就够。SSE 需要两个连接（一个收消息，一个发答案）。

### Q2: 流式推送的延迟瓶颈在哪？

**A:** 三个环节：
1. **LLM 首 token 延迟**：DeepSeek API 的 TTFT（Time To First Token）约 200-500ms
2. **网络传输**：WebSocket 逐 chunk 推送，几乎无额外延迟
3. **前端渲染**：React 状态更新 + DOM 渲染，约 16ms/帧

瓶颈在 LLM API，不在我们的代码。流式推送让用户**感知延迟**从 3 秒（等全部生成完）降到 200ms（首字出现）。

### Q3: 断线重连为什么用指数退避？

**A:** 防止**重连风暴**。如果服务端故障，100 个客户端同时重连：
- 固定间隔 1 秒：每秒 100 次请求，服务端压力大
- 指数退避：1s, 2s, 4s, 8s... 分散请求，给服务端恢复时间

数学上，指数退避保证了：
- 短暂断线：1-2 秒就重连，用户无感
- 长时间故障：不会疯狂重试，逐渐拉长间隔

### Q4: Redis 消息缓存的 key 为什么用 `ws:msgs:{session_id}`？

**A:** 每个面试会话有独立的消息队列。key 格式 `ws:msgs:{session_id}` 保证：
- 不同会话的消息互不干扰
- 可以按 session_id 精确查找和清理
- TTL 1 小时自动过期，不会永久占用内存

### Q5: 为什么用 asyncio.Queue 而不是直接在异步函数里调流式生成？

**A:** 因为 LLM SDK 的流式生成是**同步迭代器**（`for chunk in stream`），不能直接 `await`。需要在后台线程运行，通过 Queue 把 chunk 传给异步主循环：

```
后台线程（同步）: LLM stream → chunk → queue.put
主事件循环（异步）: queue.get → websocket.send
```

`call_soon_threadsafe` 是跨线程通信的关键，保证线程安全。
