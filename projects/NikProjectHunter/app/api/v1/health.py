"""
Nik Project Hunter — 健康检查 API（第三阶段）

职责：
1. 详细健康检查，输出各组件状态
2. 检查 PostgreSQL / Redis / LLM / Spider / Scheduler 状态
"""

import time
from fastapi import APIRouter
from loguru import logger

from app.config import get_settings
from app.database import engine
from sqlalchemy import text
from app.spiders.manager import spider_manager
from app.core.ai_client import ai_client

router = APIRouter(prefix="/health", tags=["health"])

settings = get_settings()


@router.get("/detail")
async def health_detail():
    """
    详细健康检查

    返回各组件的状态：
    - postgres: 数据库连接
    - redis: Redis 连接
    - llm: LLM API
    - spider: Spider 管理器
    - scheduler: 调度器
    """
    start_time = time.time()
    status = {
        "app": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running",
            "uptime_seconds": None,  # TODO: 记录启动时间
        },
        "postgres": await _check_postgres(),
        "redis": await _check_redis(),
        "llm": await _check_llm(),
        "spider": _check_spider(),
        "scheduler": _check_scheduler(),
    }

    # 整体健康状态（所有组件都健康才算 healthy）
    all_healthy = all(
        component.get("status") == "healthy"
        for component in status.values()
        if isinstance(component, dict)
    )
    status["overall"] = "healthy" if all_healthy else "degraded"
    status["check_time_ms"] = round((time.time() - start_time) * 1000, 1)

    return status


async def _check_postgres() -> dict:
    """检查 PostgreSQL 连接"""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            if result:
                return {"status": "healthy", "message": "PostgreSQL 连接正常"}
            return {"status": "degraded", "message": "数据库返回异常"}
    except Exception as e:
        logger.error(f"PostgreSQL 检查失败: {e}")
        return {"status": "unhealthy", "message": "PostgreSQL 连接失败"}


async def _check_redis() -> dict:
    """检查 Redis 连接"""
    try:
        import redis.asyncio as redis
        r = redis.from_url(settings.REDIS_URL)
        pong = await r.ping()
        await r.aclose()
        if pong:
            return {"status": "healthy", "message": "Redis 连接正常"}
        return {"status": "degraded", "message": "Redis 返回异常"}
    except ImportError:
        return {"status": "warning", "message": "redis-py 未安装"}
    except Exception as e:
        logger.error(f"Redis 检查失败: {e}")
        return {"status": "unhealthy", "message": "Redis 连接失败"}


async def _check_llm() -> dict:
    """检查 LLM API 连接"""
    if not settings.LLM_API_KEY:
        return {"status": "warning", "message": "LLM_API_KEY 未配置，AI 功能不可用"}

    try:
        # 简单调用验证
        response = await ai_client.chat(
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        if response:
            return {
                "status": "healthy",
                "message": f"LLM API 连接正常 (model={settings.LLM_MODEL})",
                "model": settings.LLM_MODEL,
                "api_base": settings.LLM_API_BASE,
            }
        return {"status": "degraded", "message": "LLM 返回为空"}
    except Exception as e:
        logger.error(f"LLM 检查失败: {e}")
        return {"status": "unhealthy", "message": "LLM API 连接失败"}


def _check_spider() -> dict:
    """检查 Spider 管理器状态"""
    status = spider_manager.status
    return {
        "status": "healthy" if status.status != "failed" else "degraded",
        "message": f"Spider 管理器状态: {status.status}",
        "spiders_registered": len(spider_manager.spiders),
        "last_crawl": {
            "crawl_id": status.crawl_id,
            "status": status.status,
            "total_found": status.total_found,
            "total_new": status.total_new,
            "error": status.error,
        },
        "spider_list": [
            {
                "name": s.name,
                "source": s.source_platform,
            }
            for s in spider_manager.spiders
        ],
    }


def _check_scheduler() -> dict:
    """检查调度器状态"""
    from app.scheduler import crawl_scheduler
    running = crawl_scheduler.scheduler.running if crawl_scheduler.scheduler else False
    return {
        "status": "healthy" if running else "warning",
        "message": "调度器运行中" if running else "调度器未启动",
        "running": running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            }
            for job in (crawl_scheduler.scheduler.get_jobs() if crawl_scheduler.scheduler else [])
        ],
    }