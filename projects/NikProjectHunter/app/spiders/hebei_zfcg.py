"""
Nik Project Hunter — 河北省政府采购网 Spider

数据源：https://www.ccgp-hebei.gov.cn/province/
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


class HebeiZFCGSpider(SpiderBase):
    """河北省政府采购网爬虫"""

    name = "hebei_zfcg"
    source_platform = "河北省政府采购网"
    base_url = "https://www.ccgp-hebei.gov.cn"

    max_pages: int = 1
    min_delay: float = 0.5
    max_delay: float = 1.5
    max_retries: int = 3
    retry_delay: float = 1.0
    max_days_ago: int = 3
    max_detail_pages: int = 30

    def __init__(self):
        super().__init__()
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30, follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )
        return self._client

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/province/"

    # ======================================================================
    # 采购意向爬取
    # ======================================================================

    async def crawl_intents(self) -> list[dict]:
        """爬取采购意向"""
        all_projects = []
        today = datetime.date.today()
        try:
            client = await self._ensure_client()
            intent_urls = [
                f"{self.base_url}/province/zfcgyxgg/zfcgyx/",
                f"{self.base_url}/province/zfcgyxgg/zfcgyx/index_1256.html",
            ]

            for intent_url in intent_urls:
                try:
                    response = await client.get(intent_url)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, "html.parser")

                    items = []
                    for a_tag in soup.find_all("a", href=True):
                        href = a_tag.get("href", "")
                        title = a_tag.get_text(strip=True)
                        if not href or not title or len(title) < 10:
                            continue
                        if "/zfcgyxgg/" not in href:
                            continue
                        if href.startswith("http"):
                            full_url = href
                        elif href.startswith("//"):
                            full_url = f"https:{href}"
                        elif href.startswith("/"):
                            full_url = f"{self.base_url}{href}"
                        elif href.startswith("../"):
                            full_url = f"{self.base_url}/{href[3:]}"
                        elif href.startswith("./"):
                            full_url = f"{self.base_url}/province/{href.lstrip('./')}"
                        else:
                            full_url = f"{self.base_url}/province/{href}"
                        items.append({
                            "title": title, "url": full_url,
                            "publish_date": self._extract_date_from_url(full_url),
                            "region": self._extract_region(full_url),
                        })

                    seen = set()
                    unique = [x for x in items if not (x["url"] in seen or seen.add(x["url"]))]
                    logger.info(f"[{self.name}] 采购意向页: {len(unique)} 条")

                    for item in unique:
                        d = item.get("publish_date", "")
                        if d:
                            try:
                                pd = datetime.datetime.strptime(d, "%Y-%m-%d").date()
                                if (today - pd).days > self.max_days_ago:
                                    continue
                            except ValueError:
                                pass
                        if len(all_projects) >= self.max_detail_pages:
                            break
                        await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))
                        try:
                            detail = await self.fetch_detail_page(item["url"])
                            if detail:
                                all_projects.append(detail)
                        except Exception as e:
                            logger.error(f"[{self.name}] 意向详情页异常: {e}")
                except Exception as e:
                    logger.warning(f"[{self.name}] 意向列表页失败 {intent_url}: {e}")
        finally:
            pass
        logger.info(f"[{self.name}] 采购意向爬取完成: {len(all_projects)} 条")
        return all_projects

    # ======================================================================
    # 采购公告爬取（原有逻辑）
    # ======================================================================

    async def fetch_homepage_items(self) -> list[dict]:
        client = await self._ensure_client()
        url = self.get_list_url(1)
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                items = []
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag.get("href", "")
                    title = a_tag.get_text(strip=True)
                    if not href or not title or len(title) < 10:
                        continue
                    if "/cggg/" not in href and "cggg" not in href:
                        continue
                    if href.endswith("/cggg/") or href.endswith("/cggg"):
                        continue
                    if href.startswith("http"):
                        full_url = href
                    elif href.startswith("//"):
                        full_url = f"https:{href}"
                    elif href.startswith("/"):
                        full_url = f"{self.base_url}{href}"
                    elif href.startswith("../"):
                        full_url = f"{self.base_url}/{href[3:]}"
                    elif href.startswith("./"):
                        full_url = f"{self.base_url}/province/{href.lstrip('./')}"
                    else:
                        full_url = f"{self.base_url}/province/{href}"
                    items.append({
                        "title": title, "url": full_url,
                        "publish_date": self._extract_date_from_url(full_url),
                        "region": self._extract_region(full_url),
                    })
                if items:
                    seen = set()
                    unique = [x for x in items if not (x["url"] in seen or seen.add(x["url"]))]
                    logger.info(f"[{self.name}] 首页提取: {len(unique)} 个唯一项目")
                    return unique
                logger.warning(f"[{self.name}] 首页无采购公告")
                return []
            except httpx.HTTPStatusError as e:
                logger.warning(f"[{self.name}] HTTP {e.response.status_code}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
            except Exception as e:
                logger.warning(f"[{self.name}] 请求失败: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
        return []

    def _extract_region(self, url: str) -> str:
        if "/province/" in url:
            return "河北（省本级）"
        city_map = {
            "sjz": "石家庄", "ts": "唐山", "qhd": "秦皇岛",
            "hd": "邯郸", "xt": "邢台", "bd": "保定",
            "zjk": "张家口", "cd": "承德", "cz": "沧州",
            "lf": "廊坊", "hs": "衡水",
        }
        for code, name in city_map.items():
            if f"/{code}/" in url:
                return f"河北（{name}）"
        return "河北"

    def _extract_date_from_url(self, url: str) -> Optional[str]:
        m = re.search(r"/20(\d{2})(\d{2})/t20\d{2}(\d{2})(\d{2})_", url)
        if m:
            return f"20{m.group(1)}-{m.group(2)}-{m.group(4)}"
        m = re.search(r"/(20\d{2})(\d{2})/", url)
        if m:
            m2 = re.search(r"t20\d{2}(\d{2})(\d{2})_", url)
            if m2:
                return f"{m.group(1)}-{m.group(2)}-{m2.group(2)}"
        return None

    async def fetch_detail_page(self, url: str) -> Optional[dict]:
        client = await self._ensure_client()
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                body_text = soup.get_text()
                title = ""
                h1 = soup.find("h1")
                if h1:
                    title = h1.get_text(strip=True)
                if not title:
                    tm = re.search(r"项目名称[：:]\s*(.+?)(?:\n|$)", body_text)
                    if tm:
                        title = tm.group(1).strip()
                publish_date = None
                for p in [r"发布时间[：:]\s*(\d{4})-(\d{1,2})-(\d{1,2})", r"(\d{4})-(\d{1,2})-(\d{1,2})"]:
                    m = re.search(p, body_text)
                    if m:
                        try:
                            publish_date = datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                            break
                        except ValueError:
                            continue
                buyer = ""
                bm = re.search(r"采购人名称[：:]\s*(.+?)(?:\n|$)", body_text)
                if bm:
                    buyer = bm.group(1).strip()
                if not buyer:
                    bm = re.search(r"采购人[：:]\s*(.+?)(?:\n|$)", body_text)
                    if bm:
                        buyer = bm.group(1).strip()
                budget = None
                for p in [r"预算金额[：:]\s*(\d+\.?\d*)\s*万元", r"采购预算金额[：:]\s*(\d+\.?\d*)", r"预算金额[：:]\s*(\d+\.?\d*)"]:
                    m = re.search(p, body_text)
                    if m:
                        try:
                            amt = float(m.group(1))
                            budget = amt * 10000 if "万元" in p else amt
                            break
                        except ValueError:
                            continue
                content = self._extract_main_content(soup)
                procurement_req = self._extract_section(soup, r"采购需求|采购用途|采购内容")
                tech_req = self._extract_section(soup, r"技术要求|技术规格")
                qual_req = self._extract_section(soup, r"资格|资质|申请人的资格要求|投标人的资格要求")
                project_bg = self._extract_section(soup, r"项目概况|项目背景")
                return {
                    "title": title, "source_url": url, "source_platform": self.source_platform,
                    "publish_date": publish_date, "region": self._extract_region(url),
                    "buyer": buyer or "", "budget": budget, "content": content,
                    "raw_html": response.text[:50000],
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
        for sel in ["div.main-content", "div.content", "div.article", "div.detail", "#content", ".content", "article", "div.news-content"]:
            elem = soup.select_one(sel)
            if elem:
                text = elem.get_text(strip=True)
                if len(text) > 100:
                    return text[:10000]
        body = soup.find("body")
        if body:
            for t in body.select("nav, .nav, .header, .footer, .sidebar, script, style"):
                t.decompose()
            return body.get_text(strip=True)[:10000]
        return soup.get_text(strip=True)[:10000]

    def _extract_section(self, soup: BeautifulSoup, pattern: str) -> str:
        for tag in ["h2", "h3", "h4", "strong", "b"]:
            section = soup.find(tag, string=re.compile(pattern))
            if section:
                parts = []
                for sib in section.find_next_siblings():
                    if sib.name in ["h2", "h3", "h4"]:
                        break
                    parts.append(sib.get_text(strip=True))
                return " ".join(parts)
        body_text = soup.get_text()
        lines = body_text.split("\n")
        in_sec = False
        parts = []
        for line in lines:
            line = line.strip()
            if re.search(pattern, line):
                in_sec = True
                continue
            if in_sec:
                if re.match(r"^(二|三|四|五|六|七|八|九|十)", line) or \
                   (re.match(r"^[A-Z]", line) and len(line) < 20):
                    break
                if line:
                    parts.append(line)
        return " ".join(parts)

    async def crawl(self) -> list[dict]:
        all_projects = []
        today = datetime.date.today()
        try:
            items = await self.fetch_homepage_items()
            if not items:
                return []
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
            logger.info(f"[{self.name}] 近期项目: {len(filtered)}/{len(items)}")
            for item in filtered[:self.max_detail_pages]:
                await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))
                try:
                    detail = await self.fetch_detail_page(item["url"])
                    if detail:
                        all_projects.append(detail)
                except Exception as e:
                    logger.error(f"[{self.name}] 详情页异常: {e}")
        finally:
            if self._client and not self._client.is_closed:
                await self._client.aclose()
                self._client = None
        logger.info(f"[{self.name}] 爬取完成: {len(all_projects)} 个项目")
        return all_projects

    # ======================================================================
    # 基类抽象方法兼容
    # ======================================================================

    async def parse_list_page(self, page) -> list[dict]:
        return []

    async def parse_detail_page(self, page) -> dict:
        return {}


async def test():
    spider = HebeiZFCGSpider()
    projects = await spider.crawl()
    print(f"\n共获取 {len(projects)} 个项目")
    for p in projects[:5]:
        print(f"  - {p['title'][:60]} | {p['buyer'][:20]} | {p['budget']} | {p['region']}")


if __name__ == "__main__":
    asyncio.run(test())
