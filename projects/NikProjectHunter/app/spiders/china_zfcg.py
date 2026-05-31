"""
Nik Project Hunter — 中国政府采购网爬虫（v6 — 纯 httpx 模式）

数据源：http://www.ccgp.gov.cn/
类型：国家级政府采购公告

策略（v6 — Intelligence Sprint 纯 httpx 版）：
- 不再使用 Playwright（容器 IP 被 WAF 拦截）
- 使用 httpx 直接请求公告列表页
- 服务端渲染 HTML 包含完整公告链接
- 解析 HTML 提取公告标题、URL、日期
- 全量公告交由 Semantic Filter + AI Intelligence 判断

注意：
- 公告列表页是服务端渲染，httpx 可获取完整列表
- 详情页同样用 httpx 请求（服务端渲染）
- 无需浏览器渲染
"""

import re
import datetime
import random
import asyncio
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from app.spiders.base.spider import SpiderBase


class ChinaZFCGSpider(SpiderBase):
    """
    中国政府采购网爬虫（v6 — 纯 httpx 模式）

    不再依赖 Playwright。
    直接 httpx 请求公告列表页，解析 HTML 提取公告链接。
    """

    name = "china_zfcg"
    source_platform = "中国政府采购网"
    base_url = "http://www.ccgp.gov.cn/"

    # 公告列表页
    LIST_URLS = [
        # 中央级公告（国家级）
        "http://www.ccgp.gov.cn/cggg/zygg/gkzb/",     # 公开招标
        "http://www.ccgp.gov.cn/cggg/zygg/jzxcs/",    # 竞争性磋商
        "http://www.ccgp.gov.cn/cggg/zygg/zbgg/",     # 中标公告
        "http://www.ccgp.gov.cn/cggg/zygg/gtgg/",     # 其他公告
        # 地方级公告
        "http://www.ccgp.gov.cn/cggg/dfgg/gkzb/",     # 公开招标
        "http://www.ccgp.gov.cn/cggg/dfgg/jzxcs/",    # 竞争性磋商
        "http://www.ccgp.gov.cn/cggg/dfgg/zbgg/",     # 中标公告
        "http://www.ccgp.gov.cn/cggg/dfgg/gtgg/",     # 其他公告
    ]

    max_pages = 1
    min_delay = 3.0
    max_delay = 6.0
    max_retries = 3

    def __init__(self):
        super().__init__()
        self._http_client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 httpx 客户端"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Referer": "http://www.ccgp.gov.cn/",
                    "Connection": "keep-alive",
                },
            )
        return self._http_client

    async def crawl(self) -> list[dict]:
        """
        重写 crawl 方法 — 不使用 Playwright
        直接用 httpx 获取公告列表 + 详情
        """
        all_projects = []
        client = await self._get_client()

        for list_url in self.LIST_URLS:
            try:
                projects = await self._fetch_list_page(client, list_url)
                logger.info(f"[{self.name}] {list_url[-20:]} 获取 {len(projects)} 条公告")

                # 逐个获取详情
                for item in projects:
                    try:
                        detail = await self._crawl_detail(item)
                        if detail:
                            all_projects.append(detail)
                    except Exception as e:
                        logger.warning(f"[{self.name}] 详情页失败: {item.get('url', '')[-40:]} - {e}")
                        continue

                # 随机延迟
                await self.random_delay()
            except Exception as e:
                logger.warning(f"[{self.name}] 列表页失败: {list_url[-30:]} - {e}")
                continue

        # 去重
        seen_urls = set()
        unique_projects = []
        for p in all_projects:
            url = p.get("source_url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                unique_projects.append(p)

        logger.info(f"[{self.name}] 共获取 {len(unique_projects)} 条唯一公告")
        return unique_projects

    async def _fetch_list_page(self, client: httpx.AsyncClient, url: str) -> list[dict]:
        """获取公告列表页并解析"""
        projects = []

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.warning(f"[{self.name}] 列表页状态码 {response.status_code}: {url[-30:]}")
                    if attempt < self.max_retries:
                        await self.random_delay()
                        continue
                    return []

                html = response.text
                soup = BeautifulSoup(html, "html.parser")

                # 查找所有公告链接（./t202*.htm 或包含 t202 的链接）
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag.get("href", "").strip()
                    title = a_tag.get_text(strip=True)

                    if not title or len(title) < 8:
                        continue
                    if not href or href.startswith("#") or href.startswith("javascript"):
                        continue
                    if "/cggg/" not in href and "t202" not in href:
                        continue

                    # 补齐 URL
                    if href.startswith("//"):
                        full_url = "https:" + href
                    elif href.startswith("/"):
                        full_url = "http://www.ccgp.gov.cn" + href
                    elif href.startswith("./"):
                        base_dir = url[:url.rfind("/") + 1] if "/" in url else url
                        full_url = base_dir + href[2:]
                    elif href.startswith("http"):
                        full_url = href
                    else:
                        continue

                    # 提取日期
                    date_str = None
                    date_match = re.search(r't(\d{8})', href)
                    if date_match:
                        try:
                            d = date_match.group(1)
                            date_str = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                        except Exception:
                            pass

                    projects.append({
                        "title": title,
                        "url": full_url,
                        "publish_date": date_str,
                    })

                # 最多 25 条
                projects = projects[:25]
                return projects

            except httpx.TimeoutException:
                logger.warning(f"[{self.name}] 列表页超时 (第{attempt}次): {url[-30:]}")
                if attempt < self.max_retries:
                    await self.random_delay()
                    continue
                return []
            except Exception as e:
                logger.warning(f"[{self.name}] 列表页异常 (第{attempt}次): {e}")
                if attempt < self.max_retries:
                    await self.random_delay()
                    continue
                return []

        return projects

    async def parse_list_page(self, page) -> list[dict]:
        """兼容接口 — 不再使用 Playwright"""
        logger.warning(f"[{self.name}] 使用 httpx 模式，忽略 Playwright parse_list_page")
        return await self.crawl()

    async def _crawl_detail(self, item: dict, page=None) -> Optional[dict]:
        """
        覆写 _crawl_detail — 使用 httpx 获取详情页
        """
        detail_url = item.get("url", "")
        if not detail_url:
            return None

        try:
            client = await self._get_client()
            response = await client.get(detail_url)
            if response.status_code != 200:
                logger.warning(f"[{self.name}] 详情页 {response.status_code}: {detail_url[-40:]}")
                return None

            html = response.text
            soup = BeautifulSoup(html, "html.parser")

            result = {
                "title": item.get("title", ""),
                "source_url": detail_url,
                "source_platform": self.source_platform,
                "publish_date": item.get("publish_date"),
                "region": None,
                "buyer": None,
                "budget": None,
                "content": None,
                "raw_html": None,
            }

            # 提取标题
            title_selectors = ["h1", ".title", ".biaoti", "#biaoti", ".detail-title", ".article-title"]
            for sel in title_selectors:
                el = soup.select_one(sel)
                if el:
                    t = el.get_text(strip=True)
                    if len(t) > 10:
                        result["title"] = t
                        break

            # 提取正文
            content_selectors = [
                "#content", ".content", ".article-content",
                ".vF_detail_content", ".detail-content",
                ".detail_text", ".text-body",
                "#main-content", ".main-content",
            ]
            for sel in content_selectors:
                el = soup.select_one(sel)
                if el:
                    result["content"] = el.get_text(strip=True)
                    result["raw_html"] = str(el)
                    break

            if not result.get("content"):
                result["content"] = soup.get_text(strip=True)[:5000]

            content_text = result.get("content") or ""

            # 采购单位
            buyer_match = re.search(r"(?:采购人|采购单位|招标人|招标单位|业主|采购方)[：:]\s*([^\s，,。.\n]{2,30})", content_text)
            if buyer_match:
                result["buyer"] = buyer_match.group(1).strip()

            # 预算（统一为元）
            budget_match = re.search(r"(?:预算金额|项目预算|预算|投资金额|采购预算)[：:]\s*([\d,]+(?:\.\d+)?)\s*(万?元?|万元)?", content_text)
            if budget_match:
                try:
                    amount = float(budget_match.group(1).replace(",", ""))
                    unit = (budget_match.group(2) or "").strip()
                    if "万" in unit:
                        amount *= 10000
                    result["budget"] = amount
                except ValueError:
                    pass

            await self.random_delay()
            return result

        except Exception as e:
            logger.warning(f"[{self.name}] 详情页异常: {detail_url[-40:]} - {e}")
            return None

    async def parse_detail_page(self, page) -> dict:
        """兼容接口 — 不再使用 Playwright"""
        logger.warning(f"[{self.name}] 使用 httpx 模式，忽略 Playwright parse_detail_page")
        return {}

    async def random_delay(self):
        """随机延迟"""
        delay = random.uniform(self.min_delay, self.max_delay)
        import asyncio
        await asyncio.sleep(delay)

    def get_list_url(self, page: int) -> str:
        """兼容 SpiderBase 抽象方法"""
        idx = (page - 1) % len(self.LIST_URLS)
        return self.LIST_URLS[idx]