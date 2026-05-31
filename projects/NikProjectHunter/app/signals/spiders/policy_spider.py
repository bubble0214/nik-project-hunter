"""
Nik Project Hunter — 政策信号爬虫（第五阶段）

监听维度：
- 国家数据局政策
- 国资委数据要素政策
- 发改委数字经济政策
- 工信部 AI 政策
- 数据安全相关法规

来源：政府官网 / 国务院 / 各部委新闻
"""

import re
from loguru import logger
from playwright.async_api import Page

from app.signals.spiders.base import SignalSpiderBase


class PolicySignalSpider(SignalSpiderBase):
    """
    政策信号爬虫

    监听国家政策动向，分析对行业的影响。
    """

    name = "policy_signal"
    signal_type = "policy"
    signal_source = "国家政策"

    # 政策发布机构
    TARGET_AGENCIES = [
        "国家数据局", "国务院", "发改委", "工信部", "国资委",
        "国务院", "网信办", "科技部", "财政部",
        "人民银行", "金融监管局", "证监会",
    ]

    # 政策关键词
    TARGET_KEYWORDS = [
        "数据要素", "数据资产", "数据治理", "数据安全",
        "数字经济", "数字化转型", "数字政府",
        "人工智能", "AI", "大模型", "智能",
        "数据交易", "数据流通", "数据确权",
        "数据入表", "数据估值",
        "信创", "国产化", "自主可控",
        "信息化", "数字化建设",
    ]

    search_url = "https://www.gov.cn/"

    # 使用聚合搜索替代
    search_url = "https://news.baidu.com/ns?word=数据要素 政策 数据局 国资委 发改委&pn=0&rn=20"

    async def parse_signals(self, page: Page) -> list[dict]:
        """
        解析百度新闻政策搜索结果
        """
        signals = []
        try:
            await page.wait_for_selector("#searcherlist", timeout=15000)
            items = await page.query_selector_all(".result")

            for item in items[:25]:
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

                    # 检查是否包含政策关键词
                    title_abstract = title + " " + abstract
                    if not any(kw.lower() in title_abstract.lower() for kw in self.TARGET_KEYWORDS):
                        continue

                    # 识别发布机构
                    agency = self._identify_agency(title, abstract)

                    signals.append({
                        "title": title,
                        "company_name": agency,  # 政策信号中，company_name 存储发布机构
                        "url": url,
                        "publish_date": source_text,
                        "abstract": abstract,
                    })

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"[政策信号] 列表页解析失败: {e}")

        return signals

    def _identify_agency(self, title: str, abstract: str) -> str:
        """识别政策发布机构"""
        text = title + " " + abstract
        for agency in self.TARGET_AGENCIES:
            if agency in text:
                return agency
        return "政策发布机构"

    async def extract_signal_detail(self, page: Page, item: dict) -> dict:
        """
        提取政策信号详情
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
                    ".detail-content",
                    ".policy-content",
                ]
                for selector in selectors:
                    el = await page.query_selector(selector)
                    if el:
                        content = await el.inner_text()
                        content = content.strip()[:3000]
                        break
            except Exception:
                pass

        return {
            "signal_type": self.signal_type,
            "company_name": item.get("company_name", "政策发布机构"),
            "title": item.get("title", ""),
            "content": content or item.get("abstract", ""),
            "source_url": detail_url or item.get("url", ""),
            "source_platform": "政府政策",
            "publish_date": item.get("publish_date", ""),
            "raw_html": None,
        }