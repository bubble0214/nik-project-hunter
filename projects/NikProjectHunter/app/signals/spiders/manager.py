"""
Nik Project Hunter — 信号爬虫管理器（第五阶段）

职责：
1. 统一调度所有信号爬虫
2. 提供采集状态追踪
3. 管理浏览器生命周期管理
"""

import uuid
from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.signals.spiders.recruitment_spider import RecruitmentSignalSpider, RecruitmentSignalSpiderSearch
from app.signals.spiders.news_spider import NewsSignalSpider
from app.signals.spiders.executive_spider import ExecutiveSignalSpider
from app.signals.spiders.policy_spider import PolicySignalSpider


class SignalCrawlStatus:
    """信号采集状态"""

    def __init__(self):
        self.crawl_id: str = ""
        self.status: str = "idle"
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.total_signals: int = 0
        self.spider_results: dict = {}
        self.error: Optional[str] = None

    def start(self):
        self.crawl_id = str(uuid.uuid4())[:8]
        self.status = "running"
        self.start_time = datetime.now()
        self.end_time = None
        self.total_signals = 0
        self.spider_results = {}
        self.error = None

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
            "total_signals": self.total_signals,
            "spider_results": self.spider_results,
            "error": self.error,
        }


class SignalManager:
    """
    信号爬虫管理器

    统一调度所有信号爬虫。
    """

    def __init__(self):
        self.spiders = [
            RecruitmentSignalSpider(),
            RecruitmentSignalSpiderSearch(),
            NewsSignalSpider(),
            ExecutiveSignalSpider(),
            PolicySignalSpider(),
        ]
        self.status = SignalCrawlStatus()

    async def crawl_all(self) -> SignalCrawlStatus:
        """
        运行所有信号爬虫

        Returns:
            采集状态
        """
        self.status.start()
        logger.info("=" * 60)
        logger.info("🚀 开始全量信号采集")
        logger.info("=" * 60)

        all_signals = []

        try:
            for spider in self.spiders:
                spider_name = spider.name
                logger.info(f"\n{'=' * 40}")
                logger.info(f"🕵️  启动信号爬虫: {spider.signal_source} ({spider_name})")
                logger.info(f"{'=' * 40}")

                try:
                    signals = await spider.crawl()
                    all_signals.extend(signals)

                    self.status.spider_results[spider_name] = {
                        "source": spider.signal_source,
                        "type": spider.signal_type,
                        "found": len(signals),
                    }
                    self.status.total_signals += len(signals)

                    logger.info(
                        f"✅ [{spider.signal_source}] 采集 {len(signals)} 个信号"
                    )

                except Exception as e:
                    logger.error(f"❌ [{spider.signal_source}] 采集失败: {e}")
                    self.status.spider_results[spider_name] = {
                        "source": spider.signal_source,
                        "error": str(e),
                    }

            self.status.complete()
            logger.info("\n" + "=" * 60)
            logger.info(
                f"🏁 全量信号采集完成: 共 {len(all_signals)} 个信号"
            )
            logger.info("=" * 60)

        except Exception as e:
            self.status.fail(str(e))
            logger.error(f"❌ 信号采集异常: {e}")

        return self.status, all_signals

    async def close_all(self):
        """关闭所有信号爬虫的浏览器"""
        for spider in self.spiders:
            try:
                await spider.close()
            except Exception:
                pass
        logger.info("所有信号爬虫浏览器已关闭")


# 全局单例
signal_manager = SignalManager()