"""脱敏和安全日志

对敏感信息进行脱敏处理，确保日志安全。
"""

import re
import logging
from typing import Any, Dict

# 获取安全日志记录器
security_logger = logging.getLogger("security")


def mask_phone(phone: str) -> str:
    """脱敏手机号

    Args:
        phone: 手机号

    Returns:
        脱敏后的手机号
    """
    if not phone or len(phone) < 7:
        return "***"
    return phone[:3] + "****" + phone[-4:]


def mask_email(email: str) -> str:
    """脱敏邮箱

    Args:
        email: 邮箱地址

    Returns:
        脱敏后的邮箱
    """
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = "*" * len(local)
    else:
        masked_local = local[0] + "***" + local[-1]
    return f"{masked_local}@{domain}"


def mask_id_card(id_card: str) -> str:
    """脱敏身份证号

    Args:
        id_card: 身份证号

    Returns:
        脱敏后的身份证号
    """
    if not id_card or len(id_card) < 8:
        return "***"
    return id_card[:4] + "**********" + id_card[-4:]


def mask_name(name: str) -> str:
    """脱敏姓名

    Args:
        name: 姓名

    Returns:
        脱敏后的姓名
    """
    if not name:
        return "***"
    if len(name) <= 1:
        return "*"
    return name[0] + "*" * (len(name) - 1)


def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """脱敏敏感数据

    Args:
        data: 原始数据

    Returns:
        脱敏后的数据
    """
    masked = data.copy()

    # 手机号脱敏
    if "phone" in masked:
        masked["phone"] = mask_phone(str(masked["phone"]))

    # 邮箱脱敏
    if "email" in masked:
        masked["email"] = mask_email(str(masked["email"]))

    # 身份证脱敏
    if "id_card" in masked:
        masked["id_card"] = mask_id_card(str(masked["id_card"]))

    # 姓名脱敏
    if "name" in masked:
        masked["name"] = mask_name(str(masked["name"]))

    return masked


def log_security_event(
    event_type: str,
    user_id: str = None,
    ip_address: str = None,
    details: Dict[str, Any] = None,
) -> None:
    """记录安全事件

    Args:
        event_type: 事件类型
        user_id: 用户 ID
        ip_address: IP 地址
        details: 事件详情
    """
    log_data = {
        "event": event_type,
        "user_id": user_id or "unknown",
        "ip": ip_address or "unknown",
    }

    if details:
        # 脱敏详情中的敏感信息
        log_data["details"] = mask_sensitive_data(details)

    security_logger.warning(f"Security event: {log_data}")


def log_file_upload(
    filename: str,
    user_id: str,
    file_size: int,
    success: bool,
    reason: str = None,
) -> None:
    """记录文件上传事件

    Args:
        filename: 文件名
        user_id: 用户 ID
        file_size: 文件大小
        success: 是否成功
        reason: 失败原因
    """
    log_data = {
        "event": "file_upload",
        "filename": filename,
        "user_id": user_id,
        "file_size": file_size,
        "success": success,
    }

    if reason:
        log_data["reason"] = reason

    if success:
        security_logger.info(f"File upload: {log_data}")
    else:
        security_logger.warning(f"File upload failed: {log_data}")
