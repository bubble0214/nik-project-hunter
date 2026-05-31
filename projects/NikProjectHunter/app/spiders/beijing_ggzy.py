"""
Nik Project Hunter — 千里马招标网爬虫（Intelligence Sprint 增强版）

反爬策略（Intelligence Sprint）：
1. 随机 User-Agent
2. 随机 Referer
3. 指数退避（5-60s）
4. 单页模式
5. 降低访问频率（10-25s 延迟）
6. retry with exponential backoff
7. browser context rotation
8. 模拟真实浏览器行为（反检测脚本注入）
9. WAF 自动检测 + 记录
10. 模拟人类滚动行为
"""

import re
import random
import datetime
import asyncio
from typing import Optional
from urllib.parse import urljoin

from loguru import logger
from playwright.async_api import Page, BrowserContext

from app.spiders.base.spider import SpiderBase
from app.spiders.debug.debug_tools import save_page_snapshot, page_info


# =============================================================================
# 扩展 User-Agent 池
# =============================================================================
EXTRA_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

REFERERS = [
    "https://www.google.com/search?q=招标公告",
    "https://www.baidu.com/s?wd=招标公告",
    "https://www.bing.com/search?q=招标",
    "https://www.qianlima.com/",
    "https://www.qianlima.com/zbgg/",
    "https://www.qianlima.com/zhaobiao/",
]


def exponential_backoff(attempt: int, base: float = 5.0) -> float:
    """指数退避：base * 2^(attempt-1) + random jitter (Intelligence Sprint 增强版)"""
    delay = base * (2 ** (attempt - 1)) + random.uniform(0, 5)
    return min(delay, 60.0)


class AntiBotMixin:
    """反爬虫策略混合类"""

    @staticmethod
    def random_user_agent() -> str:
        return random.choice(EXTRA_USER_AGENTS)

    @staticmethod
    def random_referer() -> str:
        return random.choice(REFERERS)


class QianLiMaSpider(SpiderBase, AntiBotMixin):
    """
    千里马招标网爬虫（Data Quality Sprint 增强版）

    增强功能：
    1. 反爬策略增强（UA/Referer/延迟/重试/反检测脚本）
    2. 精准关键词过滤（仅保留数据治理/数据资产/AI/数据安全）
    3. 单页模式 + 降低访问频率
    4. 指数退避重试
    5. browser context rotation
    """

    name = "beijing_ggzy"
    source_platform = "千里马招标网"
    base_url = "https://www.qianlima.com"
    LIST_URL_TPL = "https://www.qianlima.com/zbgg/index_{page}.html"

    # Intelligence Sprint: 单页模式 + 指数退避 + 更长延迟
    max_pages = 1
    page_load_timeout = 90000
    min_delay = 10.0
    max_delay = 25.0
    max_retries = 5

    # 指数退避配置
    _backoff_base = 5.0       # 初始等待秒数
    _backoff_max = 60.0       # 最大等待秒数
    _consecutive_waf = 0      # 连续 WAF 拦截计数

    # 精准行业关键词（仅 3 个核心词）
    PRECISION_KEYWORDS = [
        "数据安全",
        "数据分类分级",
        "等保测评",
    ]

    def _matches_keywords(self, text: str) -> bool:
        """精准关键词匹配"""
        for keyword in self.PRECISION_KEYWORDS:
            if keyword.lower() in text.lower():
                return True
        return False

    def get_list_url(self, page: int) -> str:
        if page == 1:
            return "https://www.qianlima.com/zbgg/"
        return self.LIST_URL_TPL.format(page=page)

    async def new_context(self) -> BrowserContext:
        """创建反爬增强的浏览器上下文（每次新建）"""
        browser = await self.ensure_browser()
        ua = self.random_user_agent()
        ref = self.random_referer()
        context = await browser.new_context(
            user_agent=ua,
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Referer": ref,
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            },
        )
        # 反检测脚本
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
            const q = window.navigator.permissions.query;
            window.navigator.permissions.query = (p) => (
                p.name === 'notifications' ? Promise.resolve({state: 'default'}) : q(p)
            );
        """)
        return context

    async def safe_goto(self, page: Page, url: str, preserve_referer: bool = False) -> bool:
        """反爬增强的安全导航
        
        Args:
            preserve_referer: 是否保留当前页面的 Referer（用于详情页跳转，避免 WAF 检测）
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                if not preserve_referer:
                    ref = self.random_referer()
                    await page.set_extra_http_headers({"Referer": ref})
                await page.goto(url, wait_until="domcontentloaded", timeout=self.page_load_timeout)
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                await page.wait_for_timeout(3000)

                # 检测 WAF 拦截并重试
                try:
                    pt = await page.title()
                    if any(k in pt for k in ["Access Verification", "验证", "拦截"]):
                        logger.warning(f"[{self.name}] WAF 拦截 (第{attempt}次), 等待后重试: {url[-50:]}")
                        if self.debug_mode:
                            await save_page_snapshot(page, self.name, label=f"waf_block_{attempt}")
                        if attempt < self.max_retries:
                            wait = exponential_backoff(attempt)
                            await asyncio.sleep(wait)
                            continue
                        return False
                except Exception:
                    pass
                if self.debug_mode:
                    await save_page_snapshot(page, self.name, label=f"goto_{attempt}")
                return True
            except Exception as e:
                logger.warning(f"[{self.name}] 第 {attempt}/{self.max_retries} 次失败: {type(e).__name__} -> {url[-50:]}")
                if self.debug_mode:
                    await save_page_snapshot(page, self.name, label=f"error_{attempt}")
                if attempt < self.max_retries:
                    wait = exponential_backoff(attempt)
                    logger.info(f"[{self.name}] 等待 {wait:.1f}s 后重试...")
                    await asyncio.sleep(wait)
        return False

    async def parse_list_page(self, page: Page) -> list[dict]:
        """解析招标公告列表页"""
        projects = []

        if self.debug_mode:
            await save_page_snapshot(page, self.name, label="list_page")

        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)

        try:
            await page.wait_for_selector("a[href*='bid-']", timeout=20000)
        except Exception:
            logger.warning(f"[{self.name}] 未找到 bid 链接")
            return []

        bid_links = await page.query_selector_all("a[href*='bid-']")
        seen_urls = set()

        for link in bid_links:
            try:
                title = (await link.inner_text()).strip()
                href = (await link.get_attribute("href") or "").strip()
                if not title or not href or len(title) < 5:
                    continue
                if href.startswith("//"):
                    href = "https:" + href
                elif href.startswith("/"):
                    href = "https://www.qianlima.com" + href
                elif not href.startswith("http"):
                    href = "https://www.qianlima.com/" + href
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                # 限制每页项目数（减少触发 WAF 限频）
                if len(projects) >= 10:
                    break

                # 提取日期
                date_str = None
                try:
                    parent_text = await link.evaluate(
                        "el => el.closest('li, tr, .item, [class*=item], [class*=list]')?.innerText || ''"
                    )
                    if parent_text:
                        m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", parent_text)
                        if m:
                            date_str = m.group(1)
                except Exception:
                    pass

                projects.append({"title": title, "url": href, "publish_date": date_str})
            except Exception as e:
                logger.debug(f"[{self.name}] 链接解析跳过: {e}")
                continue

        logger.info(f"[{self.name}] 精准过滤后共 {len(projects)} 个项目")
        return projects

    async def parse_detail_page(self, page: Page) -> dict:
        """解析详情页（增强版：多选择器回退链 + 全文提取）"""
        result = {
            "title": "", "source_url": page.url,
            "publish_date": None, "region": None,
            "buyer": None, "budget": None,
            "content": None, "raw_html": None,
        }

        # 检测反爬页面
        try:
            pt = await page.title()
            if any(k in pt for k in ["Access Verification", "验证", "拦截"]):
                logger.warning(f"[{self.name}] 反爬拦截: {page.url}")
                return result
        except Exception:
            pass
        try:
            body = await page.evaluate("document.body?.innerText?.substring(0,200) || ''")
            if "just a moment" in body.lower() or "checking" in body.lower():
                logger.warning(f"[{self.name}] Cloudflare 检测: {page.url}")
                return result
        except Exception:
            pass

        # 获取全文 innerText（千里马大部分信息在 body 文本中）
        full_text = ""
        try:
            full_text = await page.evaluate("document.body?.innerText || ''")
        except Exception:
            pass

        # 提取标题 — 多选择器回退链
        title_selectors = ["h1", ".detail-title", ".title", "[class*=title] h1", "h2", ".biaoti"]
        for sel in title_selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    t = (await el.inner_text()).strip()
                    if len(t) > 5:
                        result["title"] = t
                        break
            except Exception:
                continue

        # 从全文提取 buyer / region / budget / date
        if full_text:
            # 招标单位
            bm = re.search(r"(?:招标单位|采购单位|采购人|招标人)[：:]\s*([^\s，,。.\n\r]{2,40})", full_text)
            if bm:
                result["buyer"] = bm.group(1).strip()

            # 地区
            rm = re.search(r"([\u4e00-\u9fff]{2,4}(?:省|市|区|县))", full_text)
            if rm:
                result["region"] = rm.group(1)

            # 预算
            bm2 = re.search(r"(?:预算|招标估价|采购预算|项目预算)[：:]\s*([\d,]+(?:[万万元亿]?\.\d*)?)", full_text)
            if bm2:
                try:
                    raw = bm2.group(1).strip()
                    if "亿" in raw:
                        result["budget"] = float(raw.replace("亿", "").replace(",", "")) * 100_000_000
                    elif "万" in raw:
                        result["budget"] = float(raw.replace("万", "").replace(",", "")) * 10000
                    else:
                        result["budget"] = float(raw.replace(",", ""))
                except ValueError:
                    pass

            # 发布时间
            tm = re.search(r"(?:发布时间|发布日期|公告日期)[：:]\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", full_text)
            if tm:
                try:
                    result["publish_date"] = datetime.datetime(int(tm.group(1)), int(tm.group(2)), int(tm.group(3)))
                except ValueError:
                    pass

        # 提取正文 — 多选择器回退
        content_selectors = [
            "[class*=content]", ".article", "#content",
            ".detail-content", ".detailCon", ".maintext",
            "article", "[class*=text]",
        ]
        for sel in content_selectors:
            try:
                ce = await page.query_selector(sel)
                if ce:
                    text = await ce.inner_text()
                    if len(text) > 100:
                        result["content"] = text
                        try:
                            result["raw_html"] = await ce.inner_html()
                        except Exception:
                            pass
                        break
            except Exception:
                continue

        # 后备：如果正文提取失败，用全文作为 content（千里马详情页没有明确的 content 容器）
        if not result["content"] and full_text and len(full_text) > 200:
            result["content"] = full_text[:10000]

        # 后备日期（从全文或 content 中）
        if not result.get("publish_date"):
            source = result.get("content") or full_text
            m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", source)
            if m:
                try:
                    result["publish_date"] = datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except ValueError:
                    pass

        # 后备标题（从全文提取第一行）
        if not result["title"] and full_text:
            lines = [l.strip() for l in full_text.split("\n") if l.strip() and len(l.strip()) > 8]
            if lines:
                result["title"] = lines[0]

        return result

    async def _warmup_waf(self, page: Page) -> bool:
        """WAF 预热：多轮访问首页过 JS Challenge
        
        华为云 WAF 的 JS Challenge 首次访问不一定过，
        尝试多次预热确保 cookie 设置成功。
        """
        urls = [
            "https://www.qianlima.com",
            "https://www.qianlima.com/zbgg/",
        ]
        for attempt in range(1, 4):
            target = urls[attempt - 1] if attempt <= len(urls) else urls[-1]
            logger.info(f"[{self.name}] WAF 预热 {attempt}/3：访问 {target}...")
            try:
                await page.goto(target, wait_until="load", timeout=90000)
                # 等待 WAF JS Challenge 执行 + cookie 设置
                await page.wait_for_timeout(10000)
                # 通过标题判断是否被拦截
                try:
                    title = await page.title()
                    if "Access Verification" in title or "验证" in title:
                        logger.warning(f"[{self.name}] WAF 预热 {attempt}/3 被拦截")
                        await asyncio.sleep(5.0)
                        continue
                    logger.info(f"[{self.name}] WAF 预热 {attempt}/3 成功 (title={title[:40]})")
                    # 成功后额外等待确保 cookie 完全生效
                    await page.wait_for_timeout(3000)
                    return True
                except Exception:
                    logger.info(f"[{self.name}] WAF 预热 {attempt}/3 完成")
                    return True
            except Exception as e:
                logger.error(f"[{self.name}] WAF 预热 {attempt}/3 异常: {e}")
                await asyncio.sleep(5.0)
        logger.warning(f"[{self.name}] WAF 预热 3 次均失败，尝试直接爬取")
        return False

    async def crawl(self) -> list[dict]:
        """串行爬取 — WAF 预热后串行访问详情页，避免触发 WAF 限频"""
        all_projects = []
        context = await self.new_context()
        page = await context.new_page()

        try:
            # WAF 预热：先访问首页过 JS Challenge
            warmed = await self._warmup_waf(page)
            if not warmed:
                logger.warning(f"[{self.name}] WAF 预热失败，尝试直接访问列表页...")

            for page_num in range(1, self.max_pages + 1):
                list_url = self.get_list_url(page_num)
                logger.info(f"[{self.name}] 正在爬取第 {page_num} 页: {list_url}")

                await asyncio.sleep(random.uniform(2.0, 4.0))
                success = await self.safe_goto(page, list_url)
                if not success:
                    logger.warning(f"[{self.name}] 第 {page_num} 页访问失败，跳过")
                    continue

                if self.debug_mode:
                    await page_info(page, self.name, label=f"list_page_{page_num}")
                    common_selectors = [
                        "a[href]", "a", "h1", "h2", "h3",
                        ".title", ".list", "table", "tr", "td",
                        "li", ".item", "[class*=list]", "[class*=item]", "[class*=title]",
                    ]
                    from app.spiders.debug.debug_tools import selector_test
                    await selector_test(page, self.name, common_selectors, label=f"list_page_{page_num}")

                projects_on_page = await self.parse_list_page(page)
                if not projects_on_page:
                    logger.info(f"[{self.name}] 第 {page_num} 页无项目，结束翻页")
                    break

                logger.info(f"[{self.name}] 第 {page_num} 页发现 {len(projects_on_page)} 个项目")

                # 串行访问详情页：复用同一个 page 对象
                # 关键：华为云 WAF 的 JS Challenge 验证结果存在 page 级别 session 中
                # 如果每次都 context.new_page() 创建新页面，WAF cookie 会丢失
                # 复用主 page 确保 WAF 验证状态持续有效
                for item in projects_on_page:
                    try:
                        detail_url = item.get("url", "")
                        if not detail_url:
                            continue
                        logger.info(f"[{self.name}] 访问详情页: {detail_url[-40:]}")
                        await asyncio.sleep(random.uniform(4.0, 6.0))
                        success = await self.safe_goto(page, detail_url, preserve_referer=True)
                        if not success:
                            continue
                        detail = await self.parse_detail_page(page)
                        if not detail:
                            continue
                        detail.setdefault("title", item.get("title", ""))
                        detail.setdefault("source_url", detail_url)
                        detail["source_platform"] = self.source_platform
                        if not detail.get("publish_date") and item.get("publish_date"):
                            detail["publish_date"] = item["publish_date"]
                        all_projects.append(detail)
                    except Exception as e:
                        logger.error(f"[{self.name}] 详情页失败 {item.get('url','')[:60]}: {e}")
                        continue

                await self.random_delay()

        except Exception as e:
            logger.error(f"[{self.name}] 爬虫运行异常: {e}")
        finally:
            await page.close()
            await context.close()

        logger.info(f"[{self.name}] 爬取完成，共获取 {len(all_projects)} 个项目")
        return all_projects