"""
Nik Project Hunter — 金采网爬虫（逆向修复版）

逆向结果（2026-05-19）：
1. 首页 /jcw/index 直接有 4 类公告列表
2. 采购公告在 #cgNoticeList 下的 .list-group-item
3. 标题: a[onclick*=noticeDetail] 的 innerText
4. 日期: span.float-right 的 innerText
5. 详情通过 noticeDetail(id, type) 函数打开
6. 链接为 javascript:void(0)，需要 evaluate 执行 noticeDetail

爬取策略：
1. 访问首页 /jcw/index
2. 等待 AJAX 加载完成（首页 JS 动态渲染公告列表）
3. 提取 #cgNoticeList, #zjNoticeList, #jgNoticeList, #gzNoticeList 中的项目
4. 对每个项目执行 noticeDetail() 打开详情页
5. 提取详情页数据

Data Quality Sprint 更新：
- 使用精准行业关键词（四象限）
- 降低访问频率
"""

import re
import datetime
from typing import Optional

from loguru import logger
from playwright.async_api import Page

from app.spiders.base.spider import SpiderBase


def _get_debug_tools():
    """懒加载调试工具（模块可能不存在）"""
    try:
        from app.spiders.debug.debug_tools import save_page_snapshot
        return save_page_snapshot
    except ImportError:
        return None


save_page_snapshot = _get_debug_tools()


class JinCaiWangSpider(SpiderBase):
    """
    金采网爬虫（逆向修复版 v2）

    从首页直接提取 4 类公告：
    - 采购公告 (#cgNoticeList)
    - 征集公告 (#zjNoticeList)
    - 结果公告 (#jgNoticeList)
    - 更正公告 (#gzNoticeList)
    """

    name = "jincaiwang"
    source_platform = "金采网"
    base_url = "http://www.cfcpn.com/jcw"

    HOME_URL = "http://www.cfcpn.com/jcw/index"

    max_pages = 1
    page_load_timeout = 45000
    min_delay = 2.0
    max_delay = 4.0

    NOTICE_LIST_IDS = [
        "cgNoticeList",
        "zjNoticeList",
        "jgNoticeList",
        "gzNoticeList",
    ]

    NOTICE_TYPES = {
        "cgNoticeList": "采购公告",
        "zjNoticeList": "征集公告",
        "jgNoticeList": "结果公告",
        "gzNoticeList": "更正公告",
    }

    # 列表页宽泛关键词（标题级别过滤）
    # 精简为 3 个核心关键词
    LIST_KEYWORDS = [
        "数据安全", "分类分级", "等保测评",
    ]

    # 精准行业关键词（仅 3 个核心词）
    PRECISION_KEYWORDS = [
        "数据安全",
        "数据分类分级",
        "等保测评",
    ]

    def _matches_keywords(self, text: str, keywords: list = None) -> bool:
        if keywords is None:
            keywords = self.PRECISION_KEYWORDS
        for keyword in keywords:
            if keyword.lower() in text.lower():
                return True
        return

    def get_list_url(self, page: int) -> str:
        return self.HOME_URL

    async def parse_list_page(self, page: Page) -> list[dict]:
        """解析首页公告列表（含重试逻辑）"""
        self._page_context = page
        projects = []

        # 重试逻辑：金采网 JS 渲染有间歇性失败，最多重试 3 次
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                logger.info(f"[{self.name}] 第 {attempt} 次重试加载页面...")
                try:
                    await page.goto(self.HOME_URL, wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    pass

            if self.debug_mode and save_page_snapshot:
                await save_page_snapshot(page, self.name, label="home_page")

            try:
                await page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                logger.warning(f"[{self.name}] networkidle 超时")
            await page.wait_for_timeout(3000)

            list_loaded = False
            for list_id in self.NOTICE_LIST_IDS:
                try:
                    await page.wait_for_selector(f"#{list_id} .list-group-item", timeout=10000)
                    list_loaded = True
                except Exception:
                    logger.debug(f"[{self.name}] #{list_id} 未加载")

            if list_loaded:
                break
            else:
                logger.warning(f"[{self.name}] 第 {attempt} 次尝试：公告列表均未加载")

        if not list_loaded:
            logger.warning(f"[{self.name}] 所有公告列表均未加载（{max_retries} 次重试后放弃）")
            return []

        for list_id in self.NOTICE_LIST_IDS:
            list_type = self.NOTICE_TYPES.get(list_id, "未知")
            items = await page.query_selector_all(f"#{list_id} .list-group-item")
            logger.info(f"[{self.name}] {list_type} (#{list_id}): {len(items)} 条")

            for item in items:
                try:
                    link = await item.query_selector("a[onclick*=noticeDetail]")
                    if not link:
                        continue
                    title = (await link.inner_text()).strip()
                    onclick = await link.get_attribute("onclick") or ""

                    match = re.search(r"noticeDetail\('([^']+)','([^']+)'\)", onclick)
                    if not match:
                        continue

                    notice_id = match.group(1)
                    notice_type = match.group(2)

                    if not title or len(title) < 5:
                        continue

                    # 列表页预过滤：标题至少匹配宽泛关键词才进入详情页
                    # 降低无意义请求（银行有很多营销、物业、印刷等采购）
                    if not self._matches_keywords(title, self.LIST_KEYWORDS):
                        continue

                    date_el = await item.query_selector("span.float-right")
                    date_str = None
                    if date_el:
                        date_str = (await date_el.inner_text()).strip()

                    detail_url = (
                        f"{self.base_url}/modules/sys/login/list"
                        f"?type=qbgg&noticeId={notice_id}"
                    )

                    projects.append({
                        "title": title,
                        "url": detail_url,
                        "publish_date": date_str,
                        "notice_id": notice_id,
                        "notice_type": notice_type,
                        "list_type": list_type,
                        "buyer": None,
                    })
                except Exception as e:
                    logger.debug(f"[{self.name}] 项目解析跳过: {e}")
                    continue

        logger.info(f"[{self.name}] 共发现 {len(projects)} 个匹配项目")
        return projects

    async def parse_detail_page(self, page: Page) -> dict:
        """解析公告详情页"""
        result = {
            "title": "", "source_url": page.url,
            "publish_date": None, "region": None,
            "buyer": None, "budget": None,
            "content": None, "raw_html": None,
        }

        if self.debug_mode and save_page_snapshot:
            await save_page_snapshot(page, self.name, label="detail")

        try:
            title_el = await page.query_selector("h5#title, #title, .detail-title, .article-title")
            if title_el:
                result["title"] = (await title_el.inner_text()).strip()
        except Exception:
            pass

        try:
            content_el = await page.query_selector(
                "#detail-new, .detail-content, .article-content, #content"
            )
            if content_el:
                result["content"] = await content_el.inner_text()
                result["raw_html"] = await content_el.inner_html()
        except Exception:
            pass

        content_text = result.get("content") or ""
        if content_text:
            buyer_match = re.search(
                r"(?:采购人|招标人|采购单位|招标单位|业主)[：:]\s*([^\s，,。.\n]{2,30})",
                content_text,
            )
            if buyer_match:
                result["buyer"] = buyer_match.group(1).strip()

            budget_match = re.search(
                r"(?:预算金额|项目预算|投资金额|采购预算)[：:]\s*([\d,]+(?:\.\d+)?)\s*万?元?",
                content_text,
            )
            if budget_match:
                try:
                    amount = float(budget_match.group(1).replace(",", ""))
                    if "万" in budget_match.group(0):
                        amount *= 10000
                    result["budget"] = amount
                except ValueError:
                    pass

            date_match = re.search(
                r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})",
                content_text,
            )
            if date_match:
                try:
                    result["publish_date"] = datetime.datetime(
                        int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                    )
                except ValueError:
                    pass

        return result

    async def _crawl_detail(self, item: dict, page: Page) -> Optional[dict]:
        """
        金采网详情页：直接在当前页面导航到详情 URL
        
        注意：使用 window.open 新窗口会导致 detail.js 的 AJAX 数据加载失败
        （浏览器安全策略阻止新窗口的异步请求）。
        改为在同一页面导航，detail.js 能正确触发 AJAX 并填充数据。
        """
        notice_id = item.get("notice_id", "")
        notice_type = item.get("notice_type", "1")
        unique_url = f"http://www.cfcpn.com/jcw/notice/{notice_id}" if notice_id else item.get("url", "")

        if not notice_id:
            return None

        try:
            # 记录当前页 URL（用于爬完后返回首页）
            home_url = page.url

            # 直接导航到详情页 URL（当前页面，不弹新窗口）
            detail_url = (
                f"{self.base_url}/sys/index/goUrl"
                f"?url=modules/sys/login/detail"
                f"&column={notice_type}&searchVal={notice_id}"
            )
            logger.info(f"[{self.name}] 导航到详情页: {detail_url[:120]}")
            await page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)

            # 等待 AJAX 数据加载（detail.js 调用 /noticeinfo/noticeInfo/dataNoticeList）
            # AJAX 响应可能需要 10-15 秒，用轮询方式等待标题填充
            await page.wait_for_timeout(2000)
            for _ in range(15):
                title_text = await page.evaluate(
                    '() => document.getElementById("title") ? document.getElementById("title").innerText.trim() : ""'
                )
                if len(title_text) > 5:
                    break
                await page.wait_for_timeout(1000)
            else:
                logger.warning(f"[{self.name}] 详情页标题等待超时 (notice_id={notice_id})")

            # 额外等待内容区域渲染
            await page.wait_for_timeout(1000)

            # 解析详情页
            detail = await self.parse_detail_page(page)
            detail["source_url"] = unique_url

            # 补充 source_platform（基类默认会做，但重写后需要显式设置）
            detail["source_platform"] = self.source_platform

            # 返回首页，为下一个详情页做准备
            try:
                await page.goto(home_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=10000)
                await page.wait_for_timeout(1000)
            except Exception:
                pass

            return detail

        except Exception as e:
            logger.warning(f"[{self.name}] 详情页打开失败 (notice_id={notice_id}): {e}")
            return None
