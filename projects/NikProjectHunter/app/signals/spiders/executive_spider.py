"""
Nik Project Hunter — 高管变动信号爬虫（第五阶段）

监听维度：
- CIO（首席信息官）变动
- CTO（首席技术官）变动
- CDO（首席数据官 / 数据局负责人）变动
- 数字化负责人变动
- 数据安全负责人变动

来源：百度新闻 / 企业公告 / 高管变动新闻
"""

import re
from loguru import logger
from playwright.async_api import Page

from app.signals.spiders.base import SignalSpiderBase


class ExecutiveSignalSpider(SignalSpiderBase):
    """
    高管变动信号爬虫

    监听企业高管人事变动，判断是否意味着新项目启动。
    """

    name = "executive_signal"
    signal_type = "executive"
    signal_source = "高管变动新闻"

    # 高管职位关键词
    EXECUTIVE_KEYWORDS = [
        "CIO", "首席信息官", "CTO", "首席技术官",
        "CDO", "首席数据官", "数据总监",
        "数字化负责人", "数字化转型负责人",
        "大数据局", "数据局", "大数据中心主任",
        "数据安全负责人", "信息安全负责人",
        "技术总监", "技术副总裁", "科技部总经理",
        "AI负责人", "人工智能负责人", "智能科技负责人",
    ]

    search_url = "https://news.baidu.com/ns?word=CIO CTO CDO 首席数据官 变动&pn=0&rn=20"

    async def parse_signals(self, page: Page) -> list[dict]:
        """
        解析百度新闻搜索结果中的高管变动信息
        """
        signals = []
        try:
            await page.wait_for_selector("#searcherlist", timeout=15000)
            items = await page.query_selector_all(".result")

            for item in items[:20]:
                try:
                    title_el = await item.query_selector("h3 a")
                    abstract_el = await item.query_selector(".c-summary")
                    source_el = await item.query_selector(".c-source")

                    title = await title_el.inner_text() if title_el else ""
                    url = await title_el.get_attribute("href") if title_el else ""
                    abstract = await abstract_el.inner_text() if abstract_el else ""
                    source_text = await source_el.inner_text() if source_el else ""
                    source_text = source_text.strip() if source_el else ""

                    title = title.strip()
                    abstract = abstract.strip()

                    # 检查是否包含高管关键词
                    title_abstract = title + " " + abstract
                    if not any(kw.lower() in title_abstract.lower() for kw in self.EXECUTIVE_KEYWORDS):
                        continue

                    # 提取公司名
                    company_name = self._extract_company_name(title, abstract)

                    signals.append({
                        "title": title,
                        "company_name": company_name,
                        "url": url,
                        "publish_date": source_text,
                        "abstract": abstract,
                    })

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"[高管信号] 列表页解析失败: {e}")

        return signals

    def _extract_company_name(self, title: str, abstract: str) -> str:
        """从标题或摘要中提取公司名称"""
        text = title + " " + abstract

        # 模式1: "XX公司任命CIO"
        match = re.search(r'([\u4e00-\u9fa5]{2,}(?:集团|公司|银行|保险|证券|科技|能源|电力|石化|石油))', text)
        if match:
            return match.group(1)

        # 模式2: "原XX公司CIO"
        match = re.search(r'原([\u4e00-\u9fa5]{2,10})', text)
        if match:
            return match.group(1)

        # 模式3: "XX任命"
        match = re.search(r'([\u4e00-\u9fa5]{2,10})任命', text)
        if match:
            return match.group(1)

        return "未知企业"

    async def extract_signal_detail(self, page: Page, item: dict) -> dict:
        """
        提取高管变动详情
        """
        detail_url = item.get("url", "")
        content = ""

        if detail_url:
            try:
                await self.safe_goto(page, detail_url)
                await self.random_delay()

                selectors = [
                    "article",
                    ".article-content",
                    ".content",
                    "#content",
                    ".news-content",
                ]
                for selector in selectors:
                    el = await page.query_selector(selector)
                    if el:
                        content = await el.inner_text()
                        content = content.strip()[:2000]
                        break
            except Exception:
                pass

        return {
            "signal_type": self.signal_type,
            "company_name": item.get("company_name", "未知企业"),
            "title": item.get("title", ""),
            "content": content or item.get("abstract", ""),
            "source_url": detail_url or item.get("url", ""),
            "source_platform": "百度新闻",
            "publish_date": item.get("publish_date", ""),
            "raw_html": None,
        }