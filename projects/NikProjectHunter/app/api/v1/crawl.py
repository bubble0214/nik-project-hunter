"""
Nik Project Hunter — 爬虫触发 API（第三阶段升级）

设计思路：
- 手动触发 Spider Manager 运行真实数据源爬取
- 查看爬取状态查询端点
- 分析 + 评分 + 通知流水线
- 兼容旧版本 API 路径
"""

import time
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.database import get_db
from app.schemas.project import CrawlRequest, CrawlResponse, ProjectResponse
from app.models import Project
from app.services.analyzer import analyzer_service
from app.services.scorer import scorer_service
from app.services.notifier import notifier_service
from app.spiders.manager import spider_manager

router = APIRouter(prefix="/crawl", tags=["crawl"])


# =============================================================================
# 爬取控制
# =============================================================================


@router.post("/start", response_model=dict)
async def start_crawl(
    db: AsyncSession = Depends(get_db),
):
    """
    启动全量爬取

    使用 Spider Manager 调度所有注册的 Spider
    """
    status = await spider_manager.crawl_all(db)
    return status.to_dict()


@router.get("/status", response_model=dict)
async def get_crawl_status():
    """
    查看最近一次爬取的状态
    """
    return spider_manager.status.to_dict()


# =============================================================================
# 兼容旧 API：单 URL 爬取
# =============================================================================


@router.post("/url", response_model=dict)
async def crawl_single_url(
    request: CrawlRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    （旧接口）手动爬取指定 URL
    """
    from app.services.crawler import crawler_service

    start_time = time.time()
    projects = await crawler_service.crawl_url(
        url=request.url,
        source=request.source,
        session=db,
    )
    elapsed = time.time() - start_time

    return {
        "projects_created": len(projects),
        "elapsed_seconds": round(elapsed, 2),
    }


@router.post("/all", response_model=dict)
async def crawl_all_old(
    db: AsyncSession = Depends(get_db),
):
    """
    （旧接口）爬取所有来源
    """
    status = await spider_manager.crawl_all(db)
    return status.to_dict()


# =============================================================================
# AI 分析 + 评分
# =============================================================================


@router.post("/analyze-all", response_model=dict)
async def analyze_all_projects(
    db: AsyncSession = Depends(get_db),
):
    """分析所有未分析的项目"""
    results = await analyzer_service.analyze_unanalyzed_projects(db)
    await db.commit()
    return {"message": f"分析完成 {len(results)} 个项目", "analyzed_count": len(results)}


@router.post("/score-all", response_model=dict)
async def score_all_projects(
    db: AsyncSession = Depends(get_db),
):
    """评分所有已分析但未评分的项目"""
    results = await scorer_service.score_analyzed_projects(db)
    await db.commit()
    return {"message": f"评分完成 {len(results)} 个项目", "scored_count": len(results)}


# =============================================================================
# 完整流水线
# =============================================================================


@router.post("/full-pipeline", response_model=dict)
async def run_full_pipeline(
    db: AsyncSession = Depends(get_db),
):
    """
    运行完整流水线：爬取 → AI 分析 → AI 评分 → 微信通知

    通知规则：
    - S 级项目：自动通知
    - A 级项目且 score >= 75：自动通知
    """
    start_time = time.time()
    stats = {}

    # 1. 爬取
    logger.info("[Pipeline] Step 1/4: 爬取")
    crawl_status = await spider_manager.crawl_all(db)
    if crawl_status.skipped:
        logger.warning("[Pipeline] 爬取被跳过（上一轮还在运行），终止流水线")
        elapsed = time.time() - start_time
        return {
            "message": "爬取被跳过，上一轮流水线仍在运行",
            "stats": {"skipped": True, "elapsed_seconds": round(elapsed, 2)},
        }
    stats["crawled"] = crawl_status.total_new

    # 2. AI 分析
    logger.info("[Pipeline] Step 2/4: AI 分析")
    analysis_results = await analyzer_service.analyze_unanalyzed_projects(db)
    await db.commit()
    stats["analyzed"] = len(analysis_results)

    # 3. AI 评分
    logger.info("[Pipeline] Step 3/4: AI 评分")
    score_results = await scorer_service.score_analyzed_projects(db)
    await db.commit()
    stats["scored"] = len(score_results)

    # 4. 微信通知（所有已评分项目）
    logger.info("[Pipeline] Step 4/4: 微信通知")
    notified = 0
    all_projects = await db.execute(
        select(Project).where(Project.score.isnot(None)).order_by(Project.score.desc())
    )
    for project in all_projects.scalars().all():
        if await notifier_service.notify_high_value_project(project):
            notified += 1
    stats["notified"] = notified

    elapsed = time.time() - start_time
    stats["elapsed_seconds"] = round(elapsed, 2)

    logger.info(
        f"[Pipeline] 完整流水线完成 | "
        f"新增 {stats['crawled']} | "
        f"分析 {stats['analyzed']} | "
        f"评分 {stats['scored']} | "
        f"通知 {stats['notified']} | "
        f"耗时 {stats['elapsed_seconds']}s"
    )

    return {"message": "完整流水线执行完成", "stats": stats}


# =============================================================================
# 通知测试
# =============================================================================


@router.post("/notify-test", response_model=dict)
async def test_notification(
    db: AsyncSession = Depends(get_db),
):
    """
    发送测试消息到企业微信

    用于验证 Webhook 配置是否正确
    """
    success = await notifier_service.send_test_message()
    if success:
        return {"message": "测试消息发送成功，请检查企业微信群"}
    else:
        return {"message": "测试消息发送失败，请检查 WECHAT_WEBHOOK_URL 配置"}