"""统一错误码定义

所有 API 和 WebSocket 使用统一的错误码，便于前端识别和处理。
"""

from enum import StrEnum


class ErrorCode(StrEnum):
    """错误码枚举"""

    # 通用错误 (1000-1099)
    UNKNOWN = "1000"
    INVALID_REQUEST = "1001"

    # 会话相关 (1100-1199)
    SESSION_NOT_FOUND = "1100"
    SESSION_INVALID_STATE = "1101"
    SESSION_ALREADY_EXISTS = "1102"

    # 解析相关 (1200-1299)
    PARSE_FAILED = "1200"
    PARSE_FILE_TOO_LARGE = "1201"
    PARSE_INVALID_FORMAT = "1202"

    # 诊断相关 (1300-1399)
    DIAGNOSE_FAILED = "1300"
    DIAGNOSE_NO_POINTS = "1301"

    # 面试相关 (1400-1499)
    INTERVIEW_NOT_STARTED = "1400"
    INTERVIEW_ALREADY_COMPLETED = "1401"
    INTERVIEW_NO_POINTS = "1402"
    INTERVIEW_INVALID_POINT = "1403"

    # LLM 相关 (1500-1599)
    LLM_UNAVAILABLE = "1500"
    LLM_TIMEOUT = "1501"
    LLM_RATE_LIMIT = "1502"

    # WebSocket 相关 (1600-1699)
    WS_INVALID_MESSAGE = "1600"
    WS_EMPTY_ANSWER = "1601"


class ErrorDetail:
    """错误详情"""

    def __init__(self, code: ErrorCode, message: str):
        self.code = code
        self.message = message

    def to_dict(self) -> dict:
        return {
            "code": self.code.value,
            "message": self.message,
        }


# 预定义错误
ERRORS = {
    ErrorCode.UNKNOWN: ErrorDetail(ErrorCode.UNKNOWN, "未知错误"),
    ErrorCode.INVALID_REQUEST: ErrorDetail(ErrorCode.INVALID_REQUEST, "请求参数无效"),

    ErrorCode.SESSION_NOT_FOUND: ErrorDetail(ErrorCode.SESSION_NOT_FOUND, "会话不存在"),
    ErrorCode.SESSION_INVALID_STATE: ErrorDetail(ErrorCode.SESSION_INVALID_STATE, "会话状态无效"),
    ErrorCode.SESSION_ALREADY_EXISTS: ErrorDetail(ErrorCode.SESSION_ALREADY_EXISTS, "会话已存在"),

    ErrorCode.PARSE_FAILED: ErrorDetail(ErrorCode.PARSE_FAILED, "简历解析失败"),
    ErrorCode.PARSE_FILE_TOO_LARGE: ErrorDetail(ErrorCode.PARSE_FILE_TOO_LARGE, "文件大小超出限制"),
    ErrorCode.PARSE_INVALID_FORMAT: ErrorDetail(ErrorCode.PARSE_INVALID_FORMAT, "文件格式不支持"),

    ErrorCode.DIAGNOSE_FAILED: ErrorDetail(ErrorCode.DIAGNOSE_FAILED, "诊断失败"),
    ErrorCode.DIAGNOSE_NO_POINTS: ErrorDetail(ErrorCode.DIAGNOSE_NO_POINTS, "没有存疑点"),

    ErrorCode.INTERVIEW_NOT_STARTED: ErrorDetail(ErrorCode.INTERVIEW_NOT_STARTED, "面试未开始"),
    ErrorCode.INTERVIEW_ALREADY_COMPLETED: ErrorDetail(ErrorCode.INTERVIEW_ALREADY_COMPLETED, "面试已结束"),
    ErrorCode.INTERVIEW_NO_POINTS: ErrorDetail(ErrorCode.INTERVIEW_NO_POINTS, "没有存疑点，无法开始面试"),
    ErrorCode.INTERVIEW_INVALID_POINT: ErrorDetail(ErrorCode.INTERVIEW_INVALID_POINT, "选中的存疑点无效"),

    ErrorCode.LLM_UNAVAILABLE: ErrorDetail(ErrorCode.LLM_UNAVAILABLE, "LLM 服务不可用"),
    ErrorCode.LLM_TIMEOUT: ErrorDetail(ErrorCode.LLM_TIMEOUT, "LLM 调用超时"),
    ErrorCode.LLM_RATE_LIMIT: ErrorDetail(ErrorCode.LLM_RATE_LIMIT, "LLM 调用频率限制"),

    ErrorCode.WS_INVALID_MESSAGE: ErrorDetail(ErrorCode.WS_INVALID_MESSAGE, "消息格式无效"),
    ErrorCode.WS_EMPTY_ANSWER: ErrorDetail(ErrorCode.WS_EMPTY_ANSWER, "回答内容不能为空"),
}


def get_error(code: ErrorCode, custom_message: str = None) -> ErrorDetail:
    """获取错误详情，可自定义消息"""
    base = ERRORS.get(code, ERRORS[ErrorCode.UNKNOWN])
    if custom_message:
        return ErrorDetail(code, custom_message)
    return base