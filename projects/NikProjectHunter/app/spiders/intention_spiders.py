"""
Nik Project Hunter — 采购意向爬虫实现（第六阶段）

支持的数据源：
1. 中国政府采购网 → 采购意向专区
2. 中央政府采购网 → 采购意向
3. 北京采购意向
4. 上海采购意向
5. 广东采购意向
6. 浙江采购意向
7. 深圳采购意向
"""

import re
import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from app.spiders.base.intention_spider import ProcurementIntentionSpider


# =============================================================================
# 1. 中国政府采购网 → 采购意向
# =============================================================================

class CCGPProcurementIntentionSpider(ProcurementIntentionSpider):
    """
    中国政府采购网 → 采购意向

    URL: http://www.ccgp.gov.cn/cggg/zygg/yxgg/ 已下架（404）
    改为通过搜索功能获取采购意向
    """

    name = "ccgp_intention"
    source_platform = "中国政府采购网(采购意向)"
    base_url = "http://www.ccgp.gov.cn/"

    INTENT_URLS = []  # 意向专区已下架，暂时跳过
    SEARCH_URL = "http://search.ccgp.gov.cn/bxsearch?searchtype=1&page_index=1&keyword=采购意向"
    min_delay = 5.0
    max_delay = 10.0

    min_delay = 4.0
    max_delay = 8.0

    async def crawl_intents(self) -> list[dict]:
        if not self.INTENT_URLS and not hasattr(self, 'SEARCH_URL'):
            logger.info(f"[{self.name}] URL 未配置，跳过")
            return []

        all_intents = []
        client = await self._get_client()

        for url in self.INTENT_URLS:
            try:
                for attempt in range(1, self.max_retries + 1):
                    try:
                        response = await client.get(url)
                        if response.status_code != 200:
                            logger.warning(f"[{self.name}] {response.status_code}: {url[-30:]}")
                            if attempt < self.max_retries:
                                await self.random_delay()
                                continue
                            break

                        html = response.text
                        soup = BeautifulSoup(html, "html.parser")

                        for a_tag in soup.find_all("a", href=True):
                            href = a_tag.get("href", "").strip()
                            title = a_tag.get_text(strip=True)
                            if not title or len(title) < 8:
                                continue
                            if not href or href.startswith("#"):
                                continue
                            if "yxgg" not in href and "t202" not in href:
                                continue

                            # 补齐 URL
                            if href.startswith("//"):
                                full_url = "https:" + href
                            elif href.startswith("/"):
                                full_url = "http://www.ccgp.gov.cn" + href
                            elif href.startswith("./"):
                                base_dir = url[:url.rfind("/") + 1]
                                full_url = base_dir + href[2:]
                            elif href.startswith("http"):
                                full_url = href
                            else:
                                continue

                            # 提取日期
                            date_str = None
                            dm = re.search(r't(\d{8})', href)
                            if dm:
                                d = dm.group(1)
                                date_str = f"{d[:4]}-{d[4:6]}-{d[6:8]}"

                            # 尝试从标题提取地区
                            region = ""
                            regions = ["北京", "上海", "广东", "浙江", "江苏", "深圳", "天津",
                                       "重庆", "四川", "湖北", "山东", "福建", "湖南", "河北"]
                            for r in regions:
                                if r in title:
                                    region = r
                                    break

                            all_intents.append({
                                "title": title,
                                "source_url": full_url,
                                "publish_date": date_str,
                                "buyer": None,
                                "region": region,
                                "estimated_budget": None,
                                "intention_content": None,
                                "annual_plan": None,
                                "construction_goal": None,
                                "technical_direction": None,
                                "budget_description": None,
                            })

                        # 最多 20 条
                        all_intents = all_intents[:20]
                        break

                    except httpx.TimeoutException:
                        logger.warning(f"[{self.name}] 超时 (第{attempt}次): {url[-30:]}")
                        if attempt < self.max_retries:
                            await self.random_delay()
                            continue
                        break

                await self.random_delay()

            except Exception as e:
                logger.error(f"[{self.name}] 列表页异常: {url[-30:]} - {e}")

        # 尝试获取详情（可选 — 采购意向详情页可能有更多信息）
        for intent in all_intents[:5]:  # 只抓前5条详情
            try:
                detail = await self._fetch_detail(client, intent["source_url"])
                if detail:
                    intent.update(detail)
                await self.random_delay()
            except Exception:
                continue

        logger.info(f"[{self.name}] 共获取 {len(all_intents)} 条采购意向")
        return all_intents

    async def _fetch_detail(self, client: httpx.AsyncClient, url: str) -> Optional[dict]:
        """获取采购意向详情页"""
        try:
            response = await client.get(url)
            if response.status_code != 200:
                return None
            soup = BeautifulSoup(response.text, "html.parser")

            # 提取正文
            content_selectors = ["#content", ".content", ".article-content",
                                 ".vF_detail_content", ".detail-content"]
            content = ""
            for sel in content_selectors:
                el = soup.select_one(sel)
                if el:
                    content = el.get_text(strip=True)
                    break
            if not content:
                content = soup.get_text(strip=True)[:5000]

            # 提取采购单位
            buyer = None
            bm = re.search(r"(?:采购人|采购单位|招标人|招标单位)[：:]\s*([^\s，,。.\n]{2,30})", content)
            if bm:
                buyer = bm.group(1).strip()

            # 提取预算
            budget = self._parse_budget(content)

            # 提取建设目标/技术方向
            goal = ""
            technical = ""
            for line in content.split("。"):
                if any(k in line for k in ["建设", "目标", "规划", "计划"]):
                    goal += line + "。"
                if any(k in line for k in ["技术", "平台", "系统", "AI", "数据", "智能"]):
                    technical += line + "。"

            return {
                "buyer": buyer,
                "estimated_budget": budget,
                "intention_content": content[:3000],
                "construction_goal": goal[:500],
                "technical_direction": technical[:500],
                "budget_description": f"预算: {budget}" if budget else "",
            }

        except Exception as e:
            logger.warning(f"[{self.name}] 详情页异常: {url[-40:]} - {e}")
            return None


# =============================================================================
# 2. 中央政府采购网 → 采购意向
# =============================================================================

class CentralGovProcurementIntentionSpider(ProcurementIntentionSpider):
    """
    中央政府采购网 → 采购意向
    URL: 待确认
    """

    name = "central_gov_intention"
    source_platform = "中央政府采购网(采购意向)"
    base_url = "https://www.zycg.gov.cn/"

    INTENT_URL = ""  # 待确认
    min_delay = 5.0
    max_delay = 10.0

    async def crawl_intents(self) -> list[dict]:
        if not self.INTENT_URL:
            logger.info(f"[{self.name}] URL 未配置，跳过")
            return []

        all_intents = []
        client = await self._get_client()

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.get(self.INTENT_URL)
                if response.status_code != 200:
                    logger.warning(f"[{self.name}] {response.status_code}")
                    if attempt < self.max_retries:
                        await self.random_delay()
                        continue
                    break

                html = response.text
                soup = BeautifulSoup(html, "html.parser")

                for a_tag in soup.find_all("a", href=True):
                    href = a_tag.get("href", "").strip()
                    title = a_tag.get_text(strip=True)
                    if not title or len(title) < 8:
                        continue
                    if not href or href.startswith("#") or href.startswith("javascript"):
                        continue

                    # 补齐 URL
                    if href.startswith("//"):
                        full_url = "https:" + href
                    elif href.startswith("/"):
                        full_url = "https://www.zycg.gov.cn" + href
                    elif href.startswith("http"):
                        full_url = href
                    else:
                        full_url = "https://www.zycg.gov.cn" + ("" if href.startswith("/") else "/") + href

                    all_intents.append({
                        "title": title,
                        "source_url": full_url,
                        "publish_date": None,
                        "buyer": None,
                        "region": "中央",
                        "estimated_budget": None,
                        "intention_content": None,
                        "annual_plan": None,
                        "construction_goal": None,
                        "technical_direction": None,
                        "budget_description": None,
                    })

                all_intents = all_intents[:15]
                break

            except Exception as e:
                logger.warning(f"[{self.name}] 请求失败 (第{attempt}次): {e}")
                if attempt < self.max_retries:
                    await self.random_delay()
                    continue
                break

        logger.info(f"[{self.name}] 共获取 {len(all_intents)} 条采购意向")
        return all_intents


# =============================================================================
# 3. 省级采购意向 — 通用模式
# =============================================================================

class ProvincialIntentionSpider(ProcurementIntentionSpider):
    """
    省级采购意向爬虫（通用）

    支持：北京、上海、广东、浙江、深圳等
    """

    name: str = ""
    source_platform: str = ""
    base_url: str = ""
    intention_url: str = ""
    region_name: str = ""

    async def crawl_intents(self) -> list[dict]:
        if not self.intention_url:
            logger.info(f"[{self.name}] URL 未配置（JS渲染站点），跳过")
            return []

        all_intents = []
        client = await self._get_client()

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.get(self.intention_url)
                if response.status_code != 200:
                    logger.warning(f"[{self.name}] {response.status_code}: {self.intention_url[-40:]}")
                    if attempt < self.max_retries:
                        await self.random_delay()
                        continue
                    break

                html = response.text
                soup = BeautifulSoup(html, "html.parser")

                for a_tag in soup.find_all("a", href=True):
                    href = a_tag.get("href", "").strip()
                    title = a_tag.get_text(strip=True)
                    if not title or len(title) < 8:
                        continue
                    if not href or href.startswith("#") or href.startswith("javascript"):
                        continue
                    # 过滤导航链接
                    clean_title = title.replace(" ", "").replace("\u00a0", "")
                    if clean_title in ("首页", "上一页", "下一页", "尾页", "当前页"):
                        continue

                    # 补齐 URL
                    if href.startswith("//"):
                        full_url = "https:" + href
                    elif href.startswith("/"):
                        base_domain = self.base_url.rstrip("/")
                        full_url = base_domain + href
                    elif href.startswith("http"):
                        full_url = href
                    else:
                        base_domain = self.base_url.rstrip("/")
                        full_url = base_domain + ("" if href.startswith("/") else "/") + href

                    # 提取日期
                    date_str = None
                    dm = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', title + href)
                    if dm:
                        date_str = f"{dm.group(1)}-{dm.group(2).zfill(2)}-{dm.group(3).zfill(2)}"

                    all_intents.append({
                        "title": title,
                        "source_url": full_url,
                        "publish_date": date_str,
                        "buyer": None,
                        "region": self.region_name,
                        "estimated_budget": None,
                        "intention_content": None,
                        "annual_plan": None,
                        "construction_goal": None,
                        "technical_direction": None,
                        "budget_description": None,
                    })

                all_intents = all_intents[:15]
                break

            except Exception as e:
                logger.warning(f"[{self.name}] 请求失败 (第{attempt}次): {e}")
                if attempt < self.max_retries:
                    await self.random_delay()
                    continue
                break

        logger.info(f"[{self.name}] 共获取 {len(all_intents)} 条采购意向")
        return all_intents


# =============================================================================
# 具体省级实现
# =============================================================================

class BeijingIntentionSpider(ProvincialIntentionSpider):
    name = "beijing_intention"
    source_platform = "北京采购意向"
    base_url = "http://www.ccgp-beijing.gov.cn/"
    intention_url = "http://www.ccgp-beijing.gov.cn/yxgk/sjcgyx/A002003001index_1.htm"
    region_name = "北京"


class ShanghaiIntentionSpider(ProvincialIntentionSpider):
    name = "shanghai_intention"
    source_platform = "上海采购意向"
    base_url = "https://www.zfcg.sh.gov.cn/"
    intention_url = ""  # 全JS渲染，需政采云API
    region_name = "上海"


class GuangdongIntentionSpider(ProvincialIntentionSpider):
    name = "guangdong_intention"
    source_platform = "广东采购意向"
    base_url = "https://gdgpo.czt.gd.gov.cn/"
    intention_url = ""  # 全JS渲染
    region_name = "广东"


class ZhejiangIntentionSpider(ProvincialIntentionSpider):
    name = "zhejiang_intention"
    source_platform = "浙江采购意向"
    base_url = "https://zfcg.czt.zj.gov.cn/"
    intention_url = ""  # 全JS渲染，需政采云API
    region_name = "浙江"


class ShenzhenIntentionSpider(ProvincialIntentionSpider):
    name = "shenzhen_intention"
    source_platform = "深圳采购意向"
    base_url = "http://www.szzfcg.cn/"
    intention_url = ""  # 404，暂时禁用
    region_name = "深圳"


# =============================================================================
# 注册所有采购意向爬虫
# =============================================================================

INTENTION_SPIDERS = [
    CCGPProcurementIntentionSpider(),
    CentralGovProcurementIntentionSpider(),
    BeijingIntentionSpider(),
    ShanghaiIntentionSpider(),
    GuangdongIntentionSpider(),
    ZhejiangIntentionSpider(),
    ShenzhenIntentionSpider(),
]
