"""
Nik Project Hunter — Spider 管理器

职责：
1. 统一调度所有已注册的 Spider
2. 提供爬取状态追踪
3. 管理浏览器生命周期（启动/关闭）
"""

import asyncio
import time
import uuid
from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.spiders.china_zfcg import ChinaZFCGSpider
from app.spiders.jincaiwang import JinCaiWangSpider
from app.spiders.beijing_ggzy import QianLiMaSpider
from app.pipeline.pipeline import Pipeline
from app.pipeline.quality_pipeline import QualityPipeline

from datetime import datetime
from app.spiders.tianjin_zfcg import TianjinZFCGSpider
from app.spiders.hebei_zfcg import HebeiZFCGSpider
from app.spiders.intention_spiders import INTENTION_SPIDERS
from app.models import ProcurementIntention
from app.services.spider_health import update_spider_health, detect_waf


# =============================================================================
# 爬取状态（Data Quality Sprint 增强版）
# =============================================================================
class CrawlStatus:
    """爬取状态追踪（Data Quality Sprint）"""

    def __init__(self):
        self.crawl_id: str = ""
        self.status: str = "idle"
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.total_found: int = 0
        self.total_new: int = 0
        self.total_filtered: int = 0
        self.spider_results: dict = {}
        self.error: Optional[str] = None
        # Data Quality Sprint 新增统计
        self.noise_filtered: int = 0
        self.keyword_filtered: int = 0
        self.llm_filtered: int = 0
        self.semantic_filtered: int = 0  # 新增：语义过滤
        self.avg_quality_score: float = 0.0

    def start(self):
        self.crawl_id = str(uuid.uuid4())[:8]
        self.status = "running"
        self.start_time = datetime.now()
        self.end_time = None
        self.total_found = 0
        self.total_new = 0
        self.total_filtered = 0
        self.spider_results = {}
        self.error = None
        self.noise_filtered = 0
        self.keyword_filtered = 0
        self.llm_filtered = 0
        self.semantic_filtered = 0
        self.avg_quality_score = 0.0

    def complete(self):
        self.status = "completed"
        self.end_time = datetime.now()

    def fail(self, error: str):
        self.status = "failed"
        self.end_time = datetime.now()
        self.error = error

    def to_dict(self) -> dict:
        return {
            "crawl_id": self.crawl_id,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "elapsed_seconds": (
                (self.end_time - self.start_time).total_seconds()
                if self.start_time and self.end_time
                else None
            ),
            "total_found": self.total_found,
            "total_new": self.total_new,
            "total_filtered": self.total_filtered,
            "noise_filtered": self.noise_filtered,
            "keyword_filtered": self.keyword_filtered,
            "llm_filtered": self.llm_filtered,
            "semantic_filtered": self.semantic_filtered,
            "avg_quality_score": round(self.avg_quality_score, 1),
            "spider_results": self.spider_results,
            "error": self.error,
        }


# =============================================================================
# Spider 管理器（Data Quality Sprint）
# =============================================================================
class SpiderManager:
    """
    Spider 管理器

    注册所有 Spider，使用 QualityPipeline 进行数据质量处理。
    """

    def __init__(self):
        self._crawl_lock = asyncio.Lock()
        self._intent_lock = asyncio.Lock()
        self.spiders = [
            ChinaZFCGSpider(),
            JinCaiWangSpider(),
            QianLiMaSpider(),
            TianjinZFCGSpider(),
            HebeiZFCGSpider(),
        ]
        self.intention_spiders = INTENTION_SPIDERS  # 采购意向爬虫
        self.status = CrawlStatus()
        self.pipeline = QualityPipeline()  # Data Quality Sprint: 使用质量管道

    async def crawl_all(self, session: AsyncSession) -> CrawlStatus:
        """
        运行所有 Spider

        Args:
            session: 数据库会话

        Returns:
            爬取状态
        """
        if self._crawl_lock.locked():
            logger.warning("[Manager] crawl_all already running, skipping")
            return self.status
        async with self._crawl_lock:
            self.status.start()
            logger.info("=" * 60)
            logger.info("🚀 开始全量爬取任务")
            logger.info("=" * 60)

            try:
                for spider in self.spiders:
                    spider_name = spider.name
                    logger.info(f"\n{'=' * 40}")
                    logger.info(f"🕷️  启动爬虫: {spider.source_platform} ({spider_name})")
                    logger.info(f"{'=' * 40}")

                    try:
                        # 运行爬虫
                        raw_projects = await spider.crawl()

                        # Data Quality Sprint: 通过质量管道处理
                        pipeline_result = await self.pipeline.process(
                            raw_projects=raw_projects,
                            source_platform=spider.source_platform,
                            session=session,
                            run_llm_filter=True,
                        )

                        # 记录结果
                        qs = pipeline_result.get("quality_scores", [])
                        avg_qs = sum(qs) / len(qs) if qs else 0
                        self.status.spider_results[spider_name] = {
                            "source": spider.source_platform,
                            "found": pipeline_result["total"],
                            "new": pipeline_result["new"],
                            "noise_filtered": pipeline_result.get("noise_filtered", 0),
                            "keyword_filtered": pipeline_result.get("keyword_filtered", 0),
                            "llm_filtered": pipeline_result.get("llm_filtered", 0),
                            "semantic_filtered": pipeline_result.get("semantic_filtered", 0),
                            "duplicates": pipeline_result.get("duplicates", 0),
                            "avg_quality_score": round(avg_qs, 1),
                        }

                        # Spider Health Intelligence 更新
                        update_spider_health(spider_name, {
                            "success": True,
                            "found": pipeline_result["total"],
                            "new": pipeline_result["new"],
                            "noise_filtered": pipeline_result.get("noise_filtered", 0),
                            "keyword_filtered": pipeline_result.get("keyword_filtered", 0),
                            "llm_filtered": pipeline_result.get("llm_filtered", 0),
                            "semantic_filtered": pipeline_result.get("semantic_filtered", 0),
                            "avg_quality_score": avg_qs,
                            "waf_detected": False,
                        })
                        self.status.semantic_filtered += pipeline_result.get("semantic_filtered", 0)
                        self.status.total_found += pipeline_result["total"]
                        self.status.total_new += pipeline_result["new"]
                        self.status.noise_filtered += pipeline_result.get("noise_filtered", 0)
                        self.status.keyword_filtered += pipeline_result.get("keyword_filtered", 0)
                        self.status.llm_filtered += pipeline_result.get("llm_filtered", 0)

                        # 更新平均质量评分
                        all_qs = []
                        for sr in self.status.spider_results.values():
                            if "avg_quality_score" in sr:
                                all_qs.append(sr["avg_quality_score"])
                        if all_qs:
                            self.status.avg_quality_score = sum(all_qs) / len(all_qs)

                        logger.info(
                            f"✅ [{spider.source_platform}] "
                            f"发现 {pipeline_result['total']} 个, "
                            f"新增 {pipeline_result['new']} 个, "
                            f"噪声过滤 {pipeline_result.get('noise_filtered', 0)} 个, "
                            f"关键词过滤 {pipeline_result.get('keyword_filtered', 0)} 个, "
                            f"LLM过滤 {pipeline_result.get('llm_filtered', 0)} 个, "
                            f"语义过滤 {pipeline_result.get('semantic_filtered', 0)} 个, "
                            f"质量评分 {avg_qs:.1f}"
                        )

                    except Exception as e:
                        logger.error(f"❌ [{spider.source_platform}] 爬取失败: {e}")
                        self.status.spider_results[spider_name] = {
                            "source": spider.source_platform,
                            "error": str(e),
                        }
                        # Spider Health: 记录失败
                        update_spider_health(spider_name, {
                            "success": False,
                            "found": 0,
                            "new": 0,
                            "noise_filtered": 0,
                            "keyword_filtered": 0,
                            "llm_filtered": 0,
                            "semantic_filtered": 0,
                            "avg_quality_score": 0,
                            "waf_detected": False,
                            "error": str(e)[:200],
                        })

            except Exception as e:
                self.status.fail(str(e))
                logger.error(f"❌ 全量爬取异常: {e}")
            else:
                self.status.complete()
                logger.info("\n" + "=" * 60)
                logger.info(
                    f"🏁 全量爬取完成: "
                    f"发现 {self.status.total_found} 个项目, "
                    f"新增 {self.status.total_new} 个"
                )
                logger.info(f"   📊 数据质量统计:")
                logger.info(f"      噪声过滤: {self.status.noise_filtered} 个")
                logger.info(f"      关键词过滤: {self.status.keyword_filtered} 个")
                logger.info(f"      语义过滤: {self.status.semantic_filtered} 个")
                logger.info(f"      LLM 过滤: {self.status.llm_filtered} 个")
                logger.info(f"      平均质量评分: {self.status.avg_quality_score:.1f}/100")
                logger.info("=" * 60)

        return self.status

    async def crawl_all_intents(self, session: AsyncSession) -> CrawlStatus:
        """运行所有 Spider 的采购意向爬取 — 直接存入 ProcurementIntention 表"""
        if self._intent_lock.locked():
            logger.warning("[Manager] crawl_all_intents already running, skipping")
            return self.status
        async with self._intent_lock:
            self.status.start()
            self.status.crawl_id = f"intent_{self.status.crawl_id}"
            logger.info("=" * 60)
            logger.info("📋 开始全量采购意向爬取任务")
            logger.info("=" * 60)

            intent_spiders = self.intention_spiders

            try:
                for spider in intent_spiders:
                    spider_name = spider.name
                    logger.info(f"\n{'=' * 40}")
                    logger.info(f"📋 采购意向: {spider.source_platform} ({spider_name})")
                    logger.info(f"{'=' * 40}")

                    try:
                        raw_intents = await spider.crawl_intents()
                        if not raw_intents:
                            logger.info(f"[{spider.source_platform}] 无采购意向数据")
                            self.status.spider_results[f"{spider_name}_intent"] = {
                                "source": f"{spider.source_platform}(采购意向)",
                                "found": 0, "new": 0,
                            }
                            continue

                        # 直接存入 ProcurementIntention 表
                        new_count = 0
                        for item in raw_intents:
                            try:
                                from sqlalchemy import select
                                result = await session.execute(
                                    select(ProcurementIntention).where(
                                        ProcurementIntention.source_url == item.get("source_url", "")
                                    )
                                )
                                if result.scalar_one_or_none():
                                    continue

                                raw_date = item.get("publish_date")
                                if isinstance(raw_date, str):
                                    try:
                                        publish_date = datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
                                    except ValueError:
                                        publish_date = None
                                else:
                                    publish_date = raw_date

                                intention = ProcurementIntention(
                                    title=item.get("title", "")[:500],
                                    source_url=item.get("source_url", ""),
                                    source=spider.source_platform,
                                    publish_date=publish_date,
                                    buyer=item.get("buyer"),
                                    region=item.get("region", ""),
                                    estimated_budget=item.get("estimated_budget"),
                                    intention_content=(item.get("intention_content") or "")[:10000],
                                    annual_plan=item.get("annual_plan", "") or "",
                                    construction_goal=item.get("construction_goal", "") or "",
                                    technical_direction=item.get("technical_direction", "") or "",
                                    budget_description=item.get("budget_description", "") or "",
                                    status="new",
                                )
                                session.add(intention)
                                new_count += 1
                            except Exception as e:
                                logger.warning(f"[{spider.source_platform}] 意向存储失败: {e}")
                                continue

                        await session.commit()

                        self.status.spider_results[f"{spider_name}_intent"] = {
                            "source": f"{spider.source_platform}(采购意向)",
                            "found": len(raw_intents),
                            "new": new_count,
                        }
                        self.status.total_found += len(raw_intents)
                        self.status.total_new += new_count

                        logger.info(
                            f"✅ [{spider.source_platform}(采购意向)] "
                            f"发现 {len(raw_intents)} 个, 新增 {new_count} 个"
                        )

                    except Exception as e:
                        logger.error(f"❌ [{spider.source_platform}(采购意向)] 爬取失败: {e}")
                        self.status.spider_results[f"{spider_name}_intent"] = {
                            "source": f"{spider.source_platform}(采购意向)",
                            "error": str(e),
                        }

                self.status.complete()
                logger.info("\n" + "=" * 60)
                logger.info(f"🏁 采购意向爬取完成: 发现 {self.status.total_found} 个, 新增 {self.status.total_new} 个")
                logger.info("=" * 60)

            except Exception as e:
                self.status.fail(str(e))
                logger.error(f"❌ 采购意向爬取异常: {e}")

        return self.status

    async def close_all(self):
        """关闭所有 Spider 的浏览器和 HTTP 客户端"""
        for spider in self.spiders:
            try:
                await spider.close_browser()
            except Exception:
                pass
            if hasattr(spider, '_http_client') and spider._http_client is not None:
                try:
                    await spider._http_client.aclose()
                except Exception:
                    pass
        logger.info("All Spider browsers and HTTP clients closed")


# 全局单例
spider_manager = SpiderManager()