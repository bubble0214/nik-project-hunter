"""
Nik Project Hunter — 数据库连接管理

设计思路：
- 异步引擎 + 异步会话，配合 FastAPI 异步特性
- pgvector 在连接时自动注册扩展
- 会话工厂模式，每个请求独立会话
- 未来扩展：多租户连接池、读写分离
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from app.config import get_settings

settings = get_settings()

# ------------------------------------------------------------------
# 异步引擎
# ------------------------------------------------------------------
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,        # 调试模式下打印 SQL
    pool_size=10,               # 连接池大小
    max_overflow=20,            # 最大溢出连接数
    pool_pre_ping=True,         # 连接前检查健康状态
)

# ------------------------------------------------------------------
# 异步会话工厂
# ------------------------------------------------------------------
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ------------------------------------------------------------------
# ORM 基类
# 所有模型继承此基类
# ------------------------------------------------------------------
Base = declarative_base()


async def get_db() -> AsyncSession:
    """
    FastAPI 依赖注入：获取数据库会话

    用法：
        @router.get("/projects")
        async def list_projects(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    初始化数据库：
    1. 创建 pgvector 扩展
    2. 创建所有表
    """
    async with engine.begin() as conn:
        # 启用 pgvector 扩展
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()