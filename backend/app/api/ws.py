"""WebSocket 路由

处理实时面试交互。
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json

router = APIRouter()

# 活跃的 WebSocket 连接
active_connections: Dict[str, Set[WebSocket]] = {}


@router.websocket("/ws/interview/{interview_id}")
async def websocket_interview(websocket: WebSocket, interview_id: str):
    """面试 WebSocket 连接

    实时传输面试问答，支持流式响应。

    Args:
        websocket: WebSocket 连接
        interview_id: 面试 ID
    """
    await websocket.accept()

    # 添加到活跃连接
    if interview_id not in active_connections:
        active_connections[interview_id] = set()
    active_connections[interview_id].add(websocket)

    try:
        while True:
            # 接收用户消息
            data = await websocket.receive_text()
            message = json.loads(data)

            # TODO: 处理面试交互
            # 1. 将回答传递给 Agent
            # 2. 流式返回下一个问题
            # 3. 发送评估反馈

            # 临时回显
            await websocket.send_json({
                "type": "echo",
                "content": message.get("content", ""),
            })

    except WebSocketDisconnect:
        # 移除连接
        active_connections[interview_id].discard(websocket)
        if not active_connections[interview_id]:
            del active_connections[interview_id]
