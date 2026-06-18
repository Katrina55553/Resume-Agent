"""数据库连接模块

使用 SQLAlchemy async engine 和 async session maker。
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=not settings.is_production,  # 生产环境关闭 SQL 日志
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,  # 自动检测断开的连接
    pool_recycle=300,
    connect_args={"timeout": 10},
)

# 创建异步会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """ORM 基类"""
    pass


async def get_db() -> AsyncSession:
    """获取数据库会话（依赖注入用）"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """初始化数据库（创建表）
    带容错处理：数据库不可用时记录警告但不阻断服务启动。
    """
    import asyncio

    for attempt in range(5):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("数据库初始化完成")
            return
        except Exception as e:
            wait = (attempt + 1) * 3
            logger.warning(
                f"数据库初始化失败 (尝试 {attempt + 1}/5): {e}，{wait}s 后重试"
            )
            await asyncio.sleep(wait)

    logger.error("数据库初始化多次失败，服务继续运行但部分功能不可用")


async def close_db() -> None:
    """关闭数据库连接"""
    await engine.dispose()
