"""简历解析异步任务

使用 Celery 处理简历解析。
"""

from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="app.tasks.parse_task.parse_resume")
def parse_resume(self, session_id: str, file_path: str) -> dict:
    """解析简历文件

    Args:
        session_id: 会话 ID
        file_path: 文件路径

    Returns:
        解析结果
    """
    # TODO: 实现简历解析逻辑
    # 1. 读取文件内容
    # 2. 调用 LLM 解析简历
    # 3. 保存解析结果到数据库
    # 4. 更新会话状态
    return {
        "session_id": session_id,
        "status": "completed",
        "parsed_data": {},
    }
