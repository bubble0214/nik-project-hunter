"""
Nik Project Hunter — 爬虫服务

设计思路：
- 使用 Playwright 爬取招投标网站动态内容
- 支持自定义 URL 和来源
- 数据提取后自动去重（基于 source_url）
- MVP 阶段只实现单页爬取，未来扩展为多页分页爬取
"""

import asyncio
import datetime
import re
from typing import Optional
from bs4 import BeautifulSoup
from loguru import logger
from playwright.async_api import async_playwright
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Project
from app.core.constants import CRAWL_SOURCES

settings = get_settings()


class CrawlerService:
    """
    项目爬虫服务

    职责：
    1. 启动浏览器实例
    2. 访问目标 URL
    3. 提取项目信息
    4. 存入数据库
    """

    def __init__(self):
        self.browser = None
        self.context = None

    async def _ensure_browser(self):
        """确保浏览器实例已启动"""
        if self.browser is None:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            self.context = await self.browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
            )

    async def crawl_url(
        self,
        url: str,
        source: str,
        session: AsyncSession,
    ) -> list[Project]:
        """
        爬取单个 URL 并提取项目

        Args:
            url: 目标页面 URL
            source: 来源名称
            session: 数据库会话

        Returns:
            新创建的 Project 列表
        """
        await self._ensure_browser()
        page = await self.context.new_page()

        try:
            logger.info(f"开始爬取: {url}")
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # 等待页面内容加载
            await page.wait_for_timeout(2000)

            # 获取页面 HTML
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            # 提取项目列表
            projects = self._extract_projects(soup, url, source)

            # 去重并保存
            created_projects = []
            for project_data in projects:
                project = await self._save_if_new(project_data, session)
                if project:
                    created_projects.append(project)

            logger.info(f"爬取完成: {url}, 找到 {len(projects)} 个项目, 新增 {len(created_projects)} 个")
            return created_projects

        except Exception as e:
            logger.error(f"爬取失败 {url}: {e}")
            return []
        finally:
            await page.close()

    def _extract_projects(
        self,
        soup: BeautifulSoup,
        base_url: str,
        source: str,
    ) -> list[dict]:
        """
        从页面 HTML 中提取项目列表

        MVP 阶段实现通用提取逻辑：
        1. 查找所有链接元素
        2. 提取标题和 URL
        3. 尝试提取发布日期和预算

        未来可针对不同来源定制提取规则。
        """
        projects = []

        # 通用提取策略：查找列表页中的链接
        for link in soup.find_all("a", href=True):
            title = link.get_text(strip=True)
            href = link["href"]

            # 过滤条件：标题长度至少 5 个字，且包含关键词
            if len(title) < 5:
                continue

            # 补齐相对 URL
            if href.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(base_url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            elif not href.startswith("http"):
                continue

            # 提取预算（如果有）
            budget = self._extract_budget(link.parent.get_text() if link.parent else "")

            # 提取日期（如果有）
            publish_date = self._extract_date(link.parent.get_text() if link.parent else "")

            projects.append({
                "title": title,
                "source_url": href,
                "source": source,
                "budget": budget,
                "publish_date": publish_date,
                "raw_html": str(link.parent) if link.parent else None,
            })

        return projects

    def _extract_budget(self, text: str) -> Optional[float]:
        """
        从文本中提取预算金额（元）
        """
        patterns = [
            r"预算[金额]*[：:]\s*(\d+[\d,.]*)\s*万",
            r"(\d+[\d,.]*)\s*万元",
            r"预算[金额]*[：:]\s*(\d+[\d,.]*)\s*元",
            r"采购预算[：:]\s*(\d+[\d,.]*)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                amount_str = match.group(1).replace(",", "")
                try:
                    amount = float(amount_str)
                    # 如果单位是万，转换为元
                    if "万" in match.group(0):
                        amount *= 10000
                    return amount
                except ValueError:
                    pass
        return None

    def _extract_date(self, text: str) -> Optional[datetime.datetime]:
        """
        从文本中提取日期
        """
        patterns = [
            r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})",
            r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})\s+(\d{1,2}):(\d{2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 3:
                        return datetime.datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                    elif len(groups) == 5:
                        return datetime.datetime(
                            int(groups[0]), int(groups[1]), int(groups[2]),
                            int(groups[3]), int(groups[4]),
                        )
                except ValueError:
                    pass
        return None

    async def _save_if_new(
        self,
        project_data: dict,
        session: AsyncSession,
    ) -> Optional[Project]:
        """
        检查是否已存在，不存在则创建
        """
        # 去重检查
        result = await session.execute(
            select(Project).where(Project.source_url == project_data["source_url"])
        )
        existing = result.scalar_one_or_none()

        if existing:
            return None

        # 创建新项目
        project = Project(**project_data)
        session.add(project)
        await session.flush()
        return project

    async def crawl_all_sources(self, session: AsyncSession) -> list[Project]:
        """
        爬取所有启用的来源
        """
        all_projects = []
        for source_config in CRAWL_SOURCES:
            if source_config["enabled"]:
                projects = await self.crawl_url(
                    url=source_config["url"],
                    source=source_config["name"],
                    session=session,
                )
                all_projects.extend(projects)
        return all_projects

    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.context = None


# 全局单例
crawler_service = CrawlerService()