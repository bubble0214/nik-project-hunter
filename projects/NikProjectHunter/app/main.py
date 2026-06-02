"""
Nik Project Hunter — FastAPI 主入口（第三阶段）

设计思路：
- 应用启动时初始化数据库和日志系统
- 注册所有路由
- 配置 CORS 和中间件
- 集成定时任务

路由注册：
- GET  / 根路径
- GET  /health 健康检查
- GET  /health/detail 详细健康检查
- /api/v1/projects/* 项目 CRUD
- /api/v1/crawl/* 爬虫控制
- /api/v1/dashboard/stats Dashboard 数据
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import get_settings
from app.database import init_db, close_db
from app.core.logging_config import setup_logging
from app.api.auth import APIKeyMiddleware
from app.api.v1 import projects, crawl
from app.api.v1.health import router as health_router
from app.api.v1.dashboard import router as dashboard_router
from app.spiders.manager import spider_manager
from app.scheduler import crawl_scheduler
from app.signals.api import router as signals_router
from app.signals.spiders.manager import signal_manager
from app.sales.api import router as sales_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时：
    - 初始化日志系统
    - 初始化数据库
    - 启动定时调度器

    关闭时：
    - 关闭定时调度器
    - 关闭数据库连接
    - 关闭爬虫浏览器
    """
    # 1. 初始化日志系统
    setup_logging()

    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 启动中...")

    # 2. 初始化数据库
    await init_db()
    logger.info("✅ 数据库初始化完成")

    # 3. 启动定时调度器
    crawl_scheduler.start()

    yield

    # 关闭资源
    crawl_scheduler.stop()
    await close_db()
    await spider_manager.close_all()
    await signal_manager.close_all()
    logger.info("👋 应用关闭")


# ------------------------------------------------------------------
# 创建 FastAPI 应用
# ------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="企业级 AI 项目情报系统 — 自动发现、AI 分析、AI 评分、微信推送招投标项目 | 第五阶段：企业信号 Intelligence",
    lifespan=lifespan,
)

# ------------------------------------------------------------------
# API Key 认证中间件（在所有 /api/v1/* 端点上强制认证）
# ------------------------------------------------------------------
app.add_middleware(APIKeyMiddleware)

# ------------------------------------------------------------------
# CORS 配置
# 生产环境应通过 CORS_ORIGINS 环境变量设置具体域名
# ------------------------------------------------------------------
cors_origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else ["*"]
allow_credentials = len(cors_origins) == 1 and cors_origins[0] != "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# 注册路由
# ------------------------------------------------------------------
app.include_router(projects.router, prefix="/api/v1")
app.include_router(crawl.router, prefix="/api/v1")
app.include_router(health_router)  # /health, /health/detail
app.include_router(dashboard_router)  # /api/v1/dashboard/*
app.include_router(signals_router)      # /api/v1/signals/*
app.include_router(sales_router)        # /api/v1/dashboard/sales*


# ------------------------------------------------------------------
# 根路径
# ------------------------------------------------------------------
@app.get("/")
async def root():
    """API 根路径"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "endpoints": {
            "health": "/health",
            "health_detail": "/health/detail",
            "projects": "/api/v1/projects",
            "crawl": "/api/v1/crawl/start",
            "dashboard": "/api/v1/dashboard/stats",
            "dashboard_intelligence": "/api/v1/dashboard/intelligence",
            "dashboard_observation": "/api/v1/dashboard/observation",
            "dashboard_observation_report": "/api/v1/dashboard/observation/report?report_type=daily",
            "signals": "/api/v1/signals",
            "signals_dashboard": "/api/v1/signals/dashboard",
            "companies": "/api/v1/signals/companies",
        },
    }


# ------------------------------------------------------------------
# 健康检查（基础版）
# ------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "version": settings.APP_VERSION}


# ------------------------------------------------------------------
# 直接运行入口（用于开发调试）
# ------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.LOG_LEVEL.lower(),
    )