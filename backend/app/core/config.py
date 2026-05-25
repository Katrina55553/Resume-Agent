"""应用配置模块

使用 pydantic-settings 从环境变量读取配置。
支持 .env 文件和系统环境变量。
"""

from typing import List
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """应用配置类"""

    # 数据库配置
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/resume_agent"

    # Redis 配置
    REDIS_URL: str = "redis://localhost:6379/0"

    # Anthropic API
    ANTHROPIC_API_KEY: str = ""

    # 安全配置
    SECRET_KEY: str = "change-me-in-production"

    # CORS 配置
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Celery 配置
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # 文件上传配置
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: str = "pdf,docx,doc,txt"

    # 限流配置
    RATE_LIMIT_PER_MINUTE: int = 60
    TOKEN_QUOTA_PER_USER: int = 100000

    # 日志级别
    LOG_LEVEL: str = "INFO"

    # 环境
    ENVIRONMENT: str = "development"

    @field_validator("CORS_ORIGINS")
    @classmethod
    def parse_cors_origins(cls, v: str) -> List[str]:
        """将逗号分隔的字符串解析为列表"""
        return [origin.strip() for origin in v.split(",")]

    @field_validator("ALLOWED_EXTENSIONS")
    @classmethod
    def parse_allowed_extensions(cls, v: str) -> List[str]:
        """将逗号分隔的字符串解析为列表"""
        return [ext.strip().lower() for ext in v.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        """获取最大上传大小（字节）"""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        """判断是否为生产环境"""
        return self.ENVIRONMENT == "production"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# 全局配置实例
settings = Settings()
