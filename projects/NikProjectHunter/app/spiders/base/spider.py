"""
Nik Project Hunter — Spider 基类

设计思路：
- 所有数据源 Spider 继承此类
- 统一管理 Playwright 浏览器生命周期（复用浏览器实例）
- 封装反爬基础策略（User-Agent 轮换、随机延迟、请求重试）
- 提供公共解析工具方法
"""

import asyncio
import random
import time
from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import urlparse

from loguru import logger
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeout,
)

from app.spiders.debug.debug_tools import save_page_snapshot, selector_test, page_info


# =============================================================================
# 常用 User-Agent 池
# =============================================================================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


class SpiderBase(ABC):
    """
    爬虫基类

    子类必须实现：
    - name: 爬虫名称
    - source_platform: 来源平台标识
    - parse_list_page(): 解析列表页
    - parse_detail_page(): 解析详情页

    子类可重写：
    - get_list_url(page): 生成列表页 URL
    - extract_projects_from_list(): 从列表页提取项目链接
    - extract_project_detail(): 从详情页提取项目信息
    """

    # ------------------------------------------------------------------
    # 子类必须定义的属性
    # ------------------------------------------------------------------
    name: str = ""                     # 爬虫名称，如 "china_zfcg"
    source_platform: str = ""          # 来源平台，如 "中国政府采购网"
    base_url: str = ""                 # 平台首页 URL
    search_url_template: str = ""      # 搜索 URL 模板（含分页占位符）

    # ------------------------------------------------------------------
    # 爬虫配置
    # ------------------------------------------------------------------
    max_pages: int = 5
    page_load_timeout: int = 30000     # 页面加载超时（毫秒）
    min_delay: float = 1.5             # 请求间最小延迟（秒）
    max_delay: float = 3.5             # 请求间最大延迟（秒）
    max_retries: int = 3               # 请求重试次数
    retry_delay: float = 2.0           # 重试等待（秒）

    # ------------------------------------------------------------------
    # Debug 配置
    # ------------------------------------------------------------------
    debug_mode: bool = False           # 调试模式：保存截图 + HTML（默认关闭，通过配置启用）
    debug_save_html: bool = True       # 保存页面 HTML
    debug_save_screenshot: bool = True # 保存页面截图

    # ------------------------------------------------------------------
    # 类级浏览器单例（所有 Spider 实例共享）
    # ------------------------------------------------------------------
    _playwright = None
    _browser: Optional[Browser] = None

    def __init__(self):
        if not self.name:
            raise ValueError("Spider 子类必须设置 name")
        if not self.source_platform:
            raise ValueError("Spider 子类必须设置 source_platform")

    # ======================================================================
    # 浏览器管理
    # ======================================================================

    @classmethod
    async def ensure_browser(cls) -> Browser:
        """确保浏览器实例已启动（类级单例）"""
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
            logger.info(f"[{cls.name}] 浏览器实例已启动")
        return cls._browser

    async def new_context(self) -> BrowserContext:
        """创建新的浏览器上下文（隔离 Cookie/缓存）"""
        browser = await self.ensure_browser()
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            # 禁用 WebDriver 检测
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        return context

    @classmethod
    async def close_browser(cls):
        """关闭浏览器实例"""
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
        logger.info(f"[{cls.name}] 浏览器实例已关闭")

    # ======================================================================
    # 反爬策略
    # ======================================================================

    async def random_delay(self):
        """随机延迟，模拟人类浏览行为"""
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)

    async def safe_goto(self, page: Page, url: str) -> bool:
        """
        安全导航 + 重试机制 + 调试快照

        - 使用 networkidle 等待（更稳定）
        - 失败时自动重试
        - 调试模式保存截图

        Returns:
            True 表示成功，False 表示失败
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                # 第一步：导航到页面
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.page_load_timeout,
                )

                # 第二步：等待网络空闲（JS 渲染完成）
                try:
                    await page.wait_for_load_state(
                        "networkidle",
                        timeout=15000,
                    )
                except Exception:
                    logger.debug(
                        f"[{self.name}] networkidle 等待超时，继续处理"
                    )

                # 第三步：额外等待 JS 渲染
                await page.wait_for_timeout(2000)

                # 调试：保存快照
                if self.debug_mode:
                    await save_page_snapshot(
                        page, self.name, label=f"goto_{attempt}"
                    )
                    await page_info(
                        page, self.name, label=f"goto_{attempt}"
                    )

                return True
            except PlaywrightTimeout:
                logger.warning(
                    f"[{self.name}] 第 {attempt}/{self.max_retries} 次超时: {url[:80]}"
                )
                if self.debug_mode:
                    await save_page_snapshot(
                        page, self.name, label=f"timeout_{attempt}"
                    )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
            except Exception as e:
                logger.error(
                    f"[{self.name}] 第 {attempt}/{self.max_retries} 次失败: {e}"
                )
                if self.debug_mode:
                    await save_page_snapshot(
                        page, self.name, label=f"error_{attempt}"
                    )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
        return False

    # ======================================================================
    # 抽象方法 — 子类必须实现
    # ======================================================================

    @abstractmethod
    def get_list_url(self, page: int) -> str:
        """
        生成第 page 页的列表页 URL

        Args:
            page: 页码（从 1 开始）

        Returns:
            完整的列表页 URL
        """
        ...

    @abstractmethod
    async def parse_list_page(self, page: Page) -> list[dict]:
        """
        解析列表页，提取项目链接

        Args:
            page: Playwright Page 对象（已导航到列表页）

        Returns:
            [{"title": str, "url": str, "publish_date": str, ...}, ...]
        """
        ...

    @abstractmethod
    async def parse_detail_page(self, page: Page) -> dict:
        """
        解析详情页，提取完整项目信息

        Args:
            page: Playwright Page 对象（已导航到详情页）

        Returns:
            {
                "title": str,
                "source_url": str,
                "publish_date": datetime or None,
                "region": str or None,
                "buyer": str or None,
                "budget": float or None,
                "content": str or None,       # 正文内容
                "raw_html": str or None,      # 原始 HTML
            }
        """
        ...

    # ======================================================================
    # 运行入口
    # ======================================================================

    async def crawl(self) -> list[dict]:
        """
        运行爬虫，返回项目数据列表

        Returns:
            [项目字典, ...]  — 每个字典是 parse_detail_page 的返回值
        """
        all_projects = []
        context = await self.new_context()
        page = await context.new_page()

        try:
            for page_num in range(1, self.max_pages + 1):
                list_url = self.get_list_url(page_num)
                logger.info(
                    f"[{self.name}] 正在爬取第 {page_num} 页: {list_url}"
                )

                # 访问列表页
                success = await self.safe_goto(page, list_url)
                if not success:
                    logger.warning(
                        f"[{self.name}] 第 {page_num} 页访问失败，跳过"
                    )
                    continue

                # 调试：页面诊断
                if self.debug_mode:
                    await page_info(
                        page, self.name, label=f"list_page_{page_num}"
                    )

                # 调试：测试常用 Selector
                if self.debug_mode:
                    common_selectors = [
                        "a[href]",
                        "a",
                        "h1",
                        "h2",
                        "h3",
                        ".title",
                        ".list",
                        "table",
                        "tr",
                        "td",
                        "li",
                        ".item",
                        "[class*=list]",
                        "[class*=item]",
                        "[class*=title]",
                    ]
                    await selector_test(
                        page,
                        self.name,
                        common_selectors,
                        label=f"list_page_{page_num}",
                    )

                # 解析列表页
                projects_on_page = await self.parse_list_page(page)
                if not projects_on_page:
                    logger.info(
                        f"[{self.name}] 第 {page_num} 页无项目，结束翻页"
                    )
                    break

                logger.info(
                    f"[{self.name}] 第 {page_num} 页发现 {len(projects_on_page)} 个项目"
                )

                # 逐个访问详情页
                for item in projects_on_page:
                    try:
                        detail = await self._crawl_detail(item, page)
                        if detail:
                            all_projects.append(detail)
                    except Exception as e:
                        logger.error(
                            f"[{self.name}] 详情页解析失败: {item.get('url', '')[:80]}: {e}"
                        )
                        continue

                # 翻页间隔
                await self.random_delay()

        except Exception as e:
            logger.error(f"[{self.name}] 爬虫运行异常: {e}")
        finally:
            await page.close()
            await context.close()

        logger.info(
            f"[{self.name}] 爬取完成，共获取 {len(all_projects)} 个项目"
        )
        return all_projects

    async def _crawl_detail(self, item: dict, page: Page) -> Optional[dict]:
        """
        爬取详情页
        """
        detail_url = item.get("url", "")
        if not detail_url:
            return None

        # 补齐完整 URL
        detail_url = self._resolve_url(detail_url)

        # 访问详情页
        success = await self.safe_goto(page, detail_url)
        if not success:
            return None

        await self.random_delay()

        # 解析详情页
        detail = await self.parse_detail_page(page)
        if not detail:
            return None

        # 合并列表页信息
        detail.setdefault("title", item.get("title", ""))
        detail.setdefault("source_url", detail_url)
        detail.setdefault("source_platform", self.source_platform)

        # 如果详情页没有提取到发布日期，使用列表页的
        if not detail.get("publish_date") and item.get("publish_date"):
            detail["publish_date"] = item["publish_date"]

        return detail

    def _resolve_url(self, url: str) -> str:
        """
        补齐相对 URL 为完整 URL
        """
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("//"):
            return f"https:{url}"
        if url.startswith("/"):
            parsed = urlparse(self.base_url)
            return f"{parsed.scheme}://{parsed.netloc}{url}"
        # 相对路径
        if not self.base_url.endswith("/"):
            return f"{self.base_url}/{url}"
        return f"{self.base_url}{url}"