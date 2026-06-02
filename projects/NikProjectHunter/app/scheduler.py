"""
Nik Project Hunter — 定时任务配置（第三阶段升级）

职责：
1. 每小时自动执行完整流水线
2. 流水线：爬取 → AI 分析 → AI 评分 → 微信通知（S/A 级 + score>=70）
3. 与 FastAPI 生命周期集成
"""

import asyncio
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session_factory
from app.models import Project
from app.spiders.manager import spider_manager
from app.services.analyzer import analyzer_service
from app.services.scorer import scorer_service
from app.services.notifier import notifier_service
from app.services.observation import generate_daily_intelligence_report, generate_weekly_intelligence_report

settings = get_settings()


class CrawlScheduler:
    """
    定时爬取调度器

    功能：
    1. 每小时执行完整流水线
    2. 自动通知高价值项目
    3. 与 FastAPI lifespan 集成
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.job_id = "crawl_pipeline"

    async def run_pipeline(self):
        """
        执行完整流水线

        流水线步骤：
        1. 爬取 → 2. AI 分析 → 3. AI 评分 → 4. 微信通知（符合规则的）
        """
        logger.info("[Scheduler] 定时任务触发：开始执行完整流水线")

        async with async_session_factory() as session:
            try:
                # =============================================================================
                # Step 1: 爬取
                # =============================================================================
                logger.info("[Scheduler] Step 1/4: 开始爬取")
                crawl_status = await spider_manager.crawl_all(session)
                logger.info(
                    f"[Scheduler] Step 1/4: 爬取完成 | "
                    f"发现 {crawl_status.total_found} 个 | "
                    f"新增 {crawl_status.total_new} 个"
                )

                # =============================================================================
                # Step 1b: 采购意向爬取 + Intelligence 分析
                # =============================================================================
                logger.info("[Scheduler] Step 1b/4: 开始采购意向爬取")
                intent_status = await spider_manager.crawl_all_intents(session)
                await session.commit()
                logger.info(
                    f"[Scheduler] Step 1b/4: 采购意向爬取完成 | "
                    f"发现 {intent_status.total_found} 个 | "
                    f"新增 {intent_status.total_new} 个"
                )

                # 采购意向 Intelligence 分析
                if intent_status.total_new > 0:
                    logger.info("[Scheduler] Step 1c/4: 开始采购意向 Intelligence 分析")
                    try:
                        from app.services.intention_intelligence import intention_intelligence_service
                        intention_results = await intention_intelligence_service.analyze_unanalyzed_intentions(session)
                        await session.commit()
                        logger.info(
                            f"[Scheduler] Step 1c/4: 意向分析完成 | "
                            f"{len(intention_results)} 个 | "
                            f"目标赛道: {sum(1 for r in intention_results if r.get('is_target', False))} 个"
                        )
                    except Exception as e:
                        logger.error(f"[Scheduler] 意向 Intelligence 分析异常: {e}")
                        await session.rollback()

                # =============================================================================
                # Step 2: AI 分析
                # =============================================================================
                logger.info("[Scheduler] Step 2/4: 开始 AI 分析")
                analysis_results = await analyzer_service.analyze_unanalyzed_projects(session)
                await session.commit()
                logger.info(
                    f"[Scheduler] Step 2/4: 分析完成 | {len(analysis_results)} 个项目"
                )

                # =============================================================================
                # Step 3: AI 评分
                # =============================================================================
                logger.info("[Scheduler] Step 3/4: 开始 AI 评分")
                score_results = await scorer_service.score_analyzed_projects(session)
                await session.commit()
                logger.info(
                    f"[Scheduler] Step 3/4: 评分完成 | {len(score_results)} 个项目"
                )

                # 汇总日志（06:00 不推送通知，10:00 日报统一发送）
                logger.info(
                    f"[Scheduler] 流水线完成 | "
                    f"新增 {crawl_status.total_new} 个 | "
                    f"分析 {len(analysis_results)} 个 | "
                    f"评分 {len(score_results)} 个"
                )



            except Exception as e:
                logger.error(f"[Scheduler] 流水线执行异常: {e}")
                await session.rollback()

    async def _notify_high_value_projects(self, session) -> int:
        """
        推送所有项目的通知

        现阶段策略：所有入库项目都推送通知
        """
        notified_count = 0

        all_projects = await session.execute(
            select(Project).where(
                Project.score.isnot(None)
            ).order_by(Project.score.desc())
        )
        for project in all_projects.scalars().all():
            if await notifier_service.notify_high_value_project(project):
                notified_count += 1

        return notified_count

    async def send_daily_report(self):
        """
        每日 10:00 CST 发送商机日报

        汇总过去 24 小时内新增的高价值项目，推送到企业微信群。
        """
        logger.info("[Scheduler] 每日商机日报开始生成")
        async with async_session_factory() as session:
            try:
                now = datetime.now(timezone(timedelta(hours=8)))
                yesterday = now - timedelta(days=1)

                # 查询过去 24 小时新增的所有项目
                result = await session.execute(
                    select(Project).where(
                        Project.created_at >= yesterday,
                        Project.score.isnot(None),
                    ).order_by(Project.score.desc())
                )
                projects = result.scalars().all()

                if not projects:
                    await notifier_service.send_report(
                        title="每日商机汇报",
                        summary="过去 24 小时无新增项目",
                        projects=[],
                    )
                    logger.info("[Scheduler] 每日商机汇报：无新增项目")
                    return

                await notifier_service.send_report(
                    title="每日商机汇报",
                    summary=f"过去 24 小时共发现 {len(projects)} 个项目",
                    projects=projects,
                )
                logger.info(
                    f"[Scheduler] 每日商机汇报推送完成 | "
                    f"共 {len(projects)} 个项目"
                )

            except Exception as e:
                logger.error(f"[Scheduler] 每日商机日报生成失败: {e}")
                await session.rollback()

    def start(self):
        """
        启动调度器

        定时任务：
        1. 每小时自动执行完整流水线（爬取 → AI 分析 → AI 评分 → 即时通知）
        2. 每天 10:00 CST 发送日报汇总（过去 24h 高价值项目）

        注意：热重载时 lifespan shutdown 会停止 scheduler，
        但 AsyncIOScheduler 不能在同一 event loop 中重新 start。
        每次重新创建实例确保 state 正确。
        """
        if self.scheduler.running:
            jobs = self.scheduler.get_jobs()
            if any(j.id == self.job_id for j in jobs):
                logger.debug("[Scheduler] 调度器已在运行")
                return
            logger.warning("[Scheduler] 调度器运行中但 job 缺失，重新初始化")
            self.scheduler.shutdown(wait=False)

        # 创建新实例，显式绑定当前 event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        self.scheduler = AsyncIOScheduler(event_loop=loop)

        # ================================================================
        # 定时任务 1：每天早上 6:00 CST 爬取 + AI 分析 + AI 评分（不推送通知）
        # ================================================================
        self.scheduler.add_job(
            self.run_pipeline,
            trigger=CronTrigger(hour=6, minute=0, timezone="Asia/Shanghai"),
            id=self.job_id,
            name="爬取流水线",
            replace_existing=True,
            misfire_grace_time=60 * 60,
        )
        logger.info("[Scheduler] 爬取流水线已注册 | 时间: 06:00 CST")

        # ================================================================
        # 定时任务 2：每天早上 10:00 CST 发送日报（汇总当日高价值项目）
        # ================================================================
        self.scheduler.add_job(
            self.send_daily_report,
            trigger=CronTrigger(hour=10, minute=0, timezone="Asia/Shanghai"),
            id="daily_report",
            name="每日商机日报",
            replace_existing=True,
            misfire_grace_time=60 * 60,
        )
        logger.info("[Scheduler] 每日商机日报已注册 | 时间: 10:00 CST")

        self.scheduler.start()
        logger.info("[Scheduler] 定时调度器已启动")

    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("[Scheduler] 定时调度器已停止")


# 全局单例
crawl_scheduler = CrawlScheduler()