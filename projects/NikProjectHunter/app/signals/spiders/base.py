"""
Nik Project Hunter — 企业信号爬虫基类（第五阶段）

设计思路：
- 所有信号爬虫继承此类
- 统一信号输出格式
- 复用 Playwright 浏览器实例（与项目爬虫共享）
- 异步采集
"""

import asyncio
import random
from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeout,
)

from app.config import get_settings

settings = get_settings()

# =============================================================================
# User-Agent 池
# =============================================================================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class SignalSpiderBase(ABC):
    """
    信号爬虫基类

    子类必须实现：
    - name: 爬虫名称
    - signal_type: 信号类型（recruitment / news / executive / policy）
    - signal_source: 信号来源描述
    - search_url: 搜索 URL
    - parse_signals(page): 解析信号列表页
    - extract_signal_detail(page): 提取单个信号详情

    输出格式：
    {
        "signal_type": str,        # recruitment / news / executive / policy
        "company_name": str,       # 关联企业名称
        "title": str,              # 信号标题
        "content": str,            # 信号内容摘要
        "source_url": str,         # 来源 URL
        "source_platform": str,    # 来源平台
        "publish_date": str,       # 发布日期（可选）
        "raw_html": str,           # 原始 HTML（可选）
    }
    """

    name: str = ""
    signal_type: str = ""
    signal_source: str = ""
    search_url: str = ""
    max_pages: int = 3
    page_load_timeout: int = 30000
    min_delay: float = 1.5
    max_delay: float = 3.0
    max_retries: int = 3

    # 类级浏览器单例（与项目爬虫共享）
    _playwright = None
    _browser: Optional[Browser] = None

    def __init__(self):
        if not self.name:
            raise ValueError("信号爬虫子类必须设置 name")
        if not self.signal_type:
            raise ValueError("信号爬虫子类必须设置 signal_type")

    # ======================================================================
    # 浏览器管理
    # ======================================================================

    @classmethod
    async def ensure_browser(cls) -> Browser:
        if cls._browser is None or not cls._browser.is_connected():
            cls._playwright = await async_playwright().start()
            cls._browser = await cls._playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                ],
            )
            logger.info(f"[{cls.name}] 信号爬虫浏览器已启动")
        return cls._browser

    async def new_context(self) -> BrowserContext:
        browser = await self.ensure_browser()
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        return context

    @classmethod
    async def close_browser(cls):
        if cls._browser:
            try:
                await cls._browser.close()
            except Exception:
                pass
            cls._browser = None
        if cls._playwright:
            try:
                await cls._playwright.stop()
            except Exception:
                pass
            cls._playwright = None
        logger.info(f"[{cls.name}] 信号爬虫浏览器已关闭")

    # ======================================================================
    # 反爬策略
    # ======================================================================

    async def random_delay(self):
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)

    async def safe_goto(self, page: Page, url: str) -> bool:
        for attempt in range(1, self.max_retries + 1):
            try:
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.page_load_timeout,
                )
                await page.wait_for_timeout(1000)
                return True
            except PlaywrightTimeout:
                logger.warning(
                    f"[{self.name}] 第 {attempt}/{self.max_retries} 次超时: {url[:80]}"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
            except Exception as e:
                logger.error(
                    f"[{self.name}] 第 {attempt}/{self.max_retries} 次失败: {e}"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
        return False

    @property
    def retry_delay(self) -> float:
        return 2.0

    # ======================================================================
    # 抽象方法
    # ======================================================================

    @abstractmethod
    async def parse_signals(self, page: Page) -> list[dict]:
        """
        解析信号列表页

        返回:
            [{"title": str, "url": str, "publish_date": str, "company_name": str, ...}, ...]
        """
        ...

    @abstractmethod
    @abstractmethod
    async def extract_signal_detail(self, page: Page, item: dict) -> dict:
        """
        提取单个信号详情

        返回:
            {
                "signal_type": str,
                "company_name": str,
                "title": str,
                "content": str,
                "source_url": str,
                "source_platform": str,
                "publish_date": str or None,
                "raw_html": str or None,
            }
        """
        ...

    # ======================================================================
    # 运行入口
    # ======================================================================

    async def crawl(self) -> list[dict]:
        """
        运行信号爬虫

        Returns:
            [信号字典, ...]
        """
        all_signals = []
        context = await self.new_context()
        page = await context.new_page()

        try:
            for page_num in range(1, self.max_pages + 1):
                url = self.search_url
                logger.info(
                    f"[{self.name}] 正在采集第 {page_num} 页信号: {url}"
                )

                success = await self.safe_goto(page, url)
                if not success:
                    logger.warning(f"[{self.name}] 第 {page_num} 页访问失败")
                    continue

                await self.random_delay()

                signals = await self.parse_signals(page)
                if not signals:
                    logger.info(f"[{self.name}] 第 {page_num} 页无新信号")
                    break

                logger.info(
                    f"[{self.name}] 第 {page_num} 页发现 {len(signals)} 个信号"
                )

                # 逐个获取详情
                for item in signals:
                    try:
                        detail = await self.extract_signal_detail(page, item)
                        if detail:
                            all_signals.append(detail)
                    except Exception as e:
                        logger.error(
                            f"[{self.name}] 信号详情提取失败: {item.get('title', '')[:50]}: {e}"
                        )
                        continue

                await self.random_delay()

        except Exception as e:
            logger.error(f"[{self.name}] 信号爬虫异常: {e}")
        finally:
            await page.close()
            await context.close()

        logger.info(
            f"[{self.name}] 采集完成，共获取 {len(all_signals)} 个信号"
        )
        return all_signals

    async def close(self):
        """关闭浏览器"""
        await self.close_browser()