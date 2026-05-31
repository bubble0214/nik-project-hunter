"""
Nik Project Hunter — 天津市政府采购网 Spider

数据源：http://tjgp.cz.tj.gov.cn/

特点：
- 纯服务端渲染，无动态加载
- 列表页 + 详情页均无 WAF/反爬
- 市级采购公告（id=1665）+ 区级采购公告（id=1664）
- 详情页通过 /viewer.do?id=XXX&ver=2 -> 302 到 documentView.do

爬取策略：
1. 用 httpx 替代 Playwright（无 JS 渲染需求，减少资源消耗）
2. 先爬市级公告（id=1665），再爬区级公告（id=1664）
3. 每页 15 条，每爬取 1 页后延迟 0.5-1.5 秒
4. 只爬当天及前 3 天的项目
"""

import asyncio
import datetime
import random
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from app.spiders.base.spider import SpiderBase


class TianjinZFCGSpider(SpiderBase):
    """
    天津市政府采购网爬虫
    """

    name = "tianjin_zfcg"
    source_platform = "天津市政府采购网"
    base_url = "http://tjgp.cz.tj.gov.cn"

    max_pages: int = 5
    page_load_timeout: int = 30000
    min_delay: float = 1.0
    max_delay: float = 2.0
    max_retries: int = 3
    retry_delay: float = 1.0

    # 只爬最近 3 天
    max_days_ago: int = 3

    def __init__(self):
        super().__init__()
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )
        return self._client

    def get_region_list_url(self, page: int, region: str = "city") -> str:
        """生成列表页 URL（含区域参数）"""
        id_map = {"city": 1665, "district": 1664}
        topic_id = id_map.get(region, 1665)
        return (
            f"{self.base_url}/portal/topicView.do"
            f"?method=view&view=Infor&id={topic_id}&ver=2&st=1&pageNum={page}"
        )

    # ======================================================================
    # 列表页解析
    # ======================================================================

    async def fetch_list_page(self, url: str) -> list[dict]:
        client = await self._ensure_client()
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
                soup = BeautifulSoup(html, "html.parser")

                items = []
                for li in soup.select("li"):
                    a_tag = li.find("a", href=True)
                    if not a_tag:
                        continue
                    href = a_tag.get("href", "")
                    title = a_tag.get_text(strip=True)
                    if not href or not title or len(title) < 5:
                        continue
                    if "/viewer.do" not in href:
                        continue

                    if href.startswith("/"):
                        full_url = f"{self.base_url}{href}"
                    elif href.startswith("http"):
                        full_url = href
                    else:
                        full_url = f"{self.base_url}/{href}"

                    # 从 li 文本提取日期
                    publish_date = self._extract_date_from_text(li.get_text())
                    items.append({
                        "title": title,
                        "url": full_url,
                        "publish_date": publish_date,
                    })

                if items:
                    logger.info(f"[{self.name}] 列表页解析成功: {len(items)} 个项目")
                    return items
                logger.warning(f"[{self.name}] 列表页无项目")
                return []

            except httpx.HTTPStatusError as e:
                logger.warning(f"[{self.name}] 第 {attempt} 次 HTTP {e.response.status_code}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
            except Exception as e:
                logger.warning(f"[{self.name}] 第 {attempt} 次失败: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
        return []

    # ======================================================================
    # 详情页解析
    # ======================================================================

    async def fetch_detail_page(self, url: str) -> Optional[dict]:
        client = await self._ensure_client()
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
                soup = BeautifulSoup(html, "html.parser")
                body_text = soup.get_text()

                # 标题
                title = ""
                h1 = soup.find("h1")
                if h1:
                    title = h1.get_text(strip=True)
                if not title:
                    title_tag = soup.find("title")
                    if title_tag:
                        title = title_tag.get_text(strip=True)

                # 发布日期
                publish_date = None
                for pattern in [
                    r"发布日期[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日",
                    r"(\d{4})-(\d{1,2})-(\d{1,2})",
                ]:
                    match = re.search(pattern, body_text)
                    if match:
                        try:
                            publish_date = datetime.datetime(
                                int(match.group(1)), int(match.group(2)), int(match.group(3))
                            )
                            break
                        except ValueError:
                            continue

                # 采购单位
                buyer = ""
                bm = re.search(r"发布来源[：:]\s*(.+?)(?:发布时间|$)", body_text)
                if bm:
                    buyer = bm.group(1).strip()

                # 预算
                budget = None
                bm2 = re.search(r"预算金额[：:]\s*(\d+\.?\d*)\s*万元", body_text)
                if bm2:
                    try:
                        budget = float(bm2.group(1)) * 10000
                    except ValueError:
                        pass
                if budget is None:
                    bm3 = re.search(r"预算金额[：:]\s*(\d+\.?\d*)", body_text)
                    if bm3:
                        try:
                            budget = float(bm3.group(1))
                        except ValueError:
                            pass

                # 正文
                content = self._extract_main_content(soup)

                # 结构化字段
                procurement_req = self._extract_section(soup, r"采购需求|项目需求|服务需求")
                tech_req = self._extract_section(soup, r"技术")
                qual_req = self._extract_section(soup, r"资格|资质|申请人的资格")
                project_bg = self._extract_section(soup, r"项目概况|项目背景")

                return {
                    "title": title,
                    "source_url": url,
                    "source_platform": self.source_platform,
                    "publish_date": publish_date,
                    "region": "天津",
                    "buyer": buyer or "",
                    "budget": budget,
                    "content": content,
                    "raw_html": html[:50000],
                    "procurement_requirements": procurement_req,
                    "technical_requirements": tech_req,
                    "qualification_requirements": qual_req,
                    "project_background": project_bg,
                }

            except httpx.HTTPStatusError as e:
                logger.warning(f"[{self.name}] 详情页 HTTP {e.response.status_code}: {url[:60]}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
            except Exception as e:
                logger.warning(f"[{self.name}] 详情页失败: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
        return None

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        for sel in ["div.main-content", "div.content", "div.article", "div.detail", "#content", ".content", "article"]:
            elem = soup.select_one(sel)
            if elem:
                text = elem.get_text(strip=True)
                if len(text) > 100:
                    return text[:10000]
        body = soup.find("body")
        if body:
            for tag in body.select("nav, .nav, .header, .footer, .sidebar, script, style"):
                tag.decompose()
            return body.get_text(strip=True)[:10000]
        return soup.get_text(strip=True)[:10000]

    def _extract_section(self, soup: BeautifulSoup, pattern: str) -> str:
        section = soup.find("h2", string=re.compile(pattern))
        if not section:
            return ""
        parts = []
        for sib in section.find_next_siblings():
            if sib.name in ["h2", "h3", "h4"]:
                break
            parts.append(sib.get_text(strip=True))
        return " ".join(parts)

    def _extract_date_from_text(self, text: str) -> Optional[str]:
        for pattern in [
            r"(\d{4})-(\d{1,2})-(\d{1,2})",
            r"(\d{4})年(\d{1,2})月(\d{1,2})日",
            r"(\d{4})/(\d{1,2})/(\d{1,2})",
        ]:
            match = re.search(pattern, text)
            if match:
                return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        return None

    # ======================================================================
    # 采购意向爬取
    # ======================================================================

    async def crawl_intents(self) -> list[dict]:
        """爬取采购意向（首页直接提取）"""
        all_projects = []
        try:
            client = await self._ensure_client()
            url = f"{self.base_url}/"
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
            soup = BeautifulSoup(html, "html.parser")

            # 首页采购意向在左侧菜单"采购意向公开"区块
            # 直接通过标题包含"采购意向公告"来识别
            items = []
            for a_tag in soup.find_all("a", href=True):
                href = a_tag.get("href", "")
                title = a_tag.get_text(strip=True)
                if not href or not title or len(title) < 10:
                    continue
                if "采购意向" not in title and "政府采购意向" not in title:
                    continue

                if href.startswith("/"):
                    full_url = f"{self.base_url}{href}"
                elif href.startswith("http"):
                    full_url = href
                else:
                    full_url = f"{self.base_url}/{href}"

                items.append({
                    "title": title,
                    "url": full_url,
                    "publish_date": self._extract_date_from_text(a_tag.get_text()),
                })

            # 去重
            seen = set()
            unique = [x for x in items if not (x["url"] in seen or seen.add(x["url"]))]
            logger.info(f"[{self.name}] 采购意向: 找到 {len(unique)} 条")

            today = datetime.date.today()
            for item in unique:
                d = item.get("publish_date", "")
                if d:
                    try:
                        pd = datetime.datetime.strptime(d, "%Y-%m-%d").date()
                        if (today - pd).days > self.max_days_ago:
                            continue
                    except ValueError:
                        pass

                await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))
                try:
                    detail = await self.fetch_detail_page(item["url"])
                    if detail:
                        all_projects.append(detail)
                except Exception as e:
                    logger.error(f"[{self.name}] 意向详情页异常: {e}")

        finally:
            pass  # client 在 crawl() 中关闭

        logger.info(f"[{self.name}] 采购意向爬取完成: {len(all_projects)} 条")
        return all_projects

    # ======================================================================
    # 爬取入口
    # ======================================================================

    async def crawl(self) -> list[dict]:
        """爬取采购公告"""
        all_projects = []
        try:
            for region_name, region_key in [("市级", "city"), ("区级", "district")]:
                logger.info(f"[{self.name}] 开始爬取{region_name}公告")
                today = datetime.date.today()

                for page_num in range(1, self.max_pages + 1):
                    list_url = self.get_region_list_url(page_num, region=region_key)
                    items = await self.fetch_list_page(list_url)
                    if not items:
                        break

                    # 时间过滤
                    filtered = []
                    for item in items:
                        d = item.get("publish_date", "")
                        if d:
                            try:
                                pd = datetime.datetime.strptime(d, "%Y-%m-%d").date()
                                if (today - pd).days > self.max_days_ago:
                                    continue
                            except ValueError:
                                pass
                        filtered.append(item)

                    if not filtered:
                        continue

                    logger.info(f"[{self.name}] {region_name} 第{page_num}页: {len(filtered)}个近期项目")

                    for item in filtered:
                        await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))
                        try:
                            detail = await self.fetch_detail_page(item["url"])
                            if detail:
                                all_projects.append(detail)
                        except Exception as e:
                            logger.error(f"[{self.name}] 详情页异常: {e}")

                    await asyncio.sleep(random.uniform(0.3, 0.8))
        finally:
            if self._client and not self._client.is_closed:
                await self._client.aclose()
                self._client = None

        logger.info(f"[{self.name}] 爬取完成: {len(all_projects)} 个项目")
        return all_projects

    # ======================================================================
    # 基类抽象方法兼容
    # ======================================================================

    def get_list_url(self, page: int) -> str:
        """基类接口：默认返回市级列表"""
        return (
            f"{self.base_url}/portal/topicView.do"
            f"?method=view&view=Infor&id=1665&ver=2&st=1&pageNum={page}"
        )

    async def parse_list_page(self, page) -> list[dict]:
        """基类接口（未使用 Playwright）"""
        return []

    async def parse_detail_page(self, page) -> dict:
        """基类接口（未使用 Playwright）"""
        return {}


# =============================================================================
# 快捷测试
# =============================================================================
async def test():
    spider = TianjinZFCGSpider()
    projects = await spider.crawl()
    print(f"\n共获取 {len(projects)} 个项目")
    for p in projects[:5]:
        print(f"  - {p['title'][:60]} | {p['buyer'][:20]} | {p['budget']}")


if __name__ == "__main__":
    asyncio.run(test())