"""
Nik Project Hunter — 新闻信号爬虫（第五阶段）

监听维度：
- 企业 AI 战略新闻
- 数字化转型新闻
- 数据战略合作
- 信息化升级
- 数据资产化动态

来源：36氪 / 虎嗅 / 百度新闻 / 企业官网新闻
"""

import re
from loguru import logger
from playwright.async_api import Page

from app.signals.spiders.base import SignalSpiderBase


class NewsSignalSpider(SignalSpiderBase):
    """
    新闻信号爬虫

    监听目标企业的 AI / 数字化 / 数据战略新闻。
    """

    name = "news_signal"
    signal_type = "news"
    signal_source = "企业新闻"

    # 目标关键词组合
    TARGET_KEYWORDS = [
        "AI", "人工智能", "大模型", "智能",
        "数字化", "数字化转型", "数据中台",
        "数据治理", "数据资产", "数据要素",
        "信息化", "智慧", "数据平台",
        "战略合作", "技术合作", "签约",
        "数据安全", "数据合规",
        "知识库", "智能客服", "智能决策",
    ]

    search_url = "https://news.baidu.com/ns?word=数据治理 AI 数字化转型&pn=0&rn=20"

    async def parse_signals(self, page: Page) -> list[dict]:
        """
        解析百度新闻搜索结果
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

                    # 提取公司名
                    company_name = self._extract_company_name(title, abstract)

                    # 过滤：只保留目标企业相关新闻
                    if not any(kw.lower() in title.lower() or kw.lower() in abstract.lower()
                               for kw in self.TARGET_KEYWORDS):
                        continue

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
            logger.error(f"[新闻信号] 列表页解析失败: {e}")

        return signals

    def _extract_company_name(self, title: str, abstract: str) -> str:
        """从标题或摘要中提取公司名称"""
        text = title + " " + abstract

        # 模式1: "XX公司发布AI战略"
        match = re.search(r'([\u4e00-\u9fa5]{2,}(?:集团|公司|银行|保险|证券|科技|能源|电力|石化|石油))', text)
        if match:
            return match.group(1)

        # 模式2: "XX与YY合作"
        match = re.search(r'([\u4e00-\u9fa5]{2,10})与', text)
        if match:
            return match.group(1)

        # 模式3: "XX："
        match = re.search(r'([\u4e00-\u9fa5]{2,10})[：:]', text)
        if match:
            return match.group(1)

        return "未知企业"

    async def extract_signal_detail(self, page: Page, item: dict) -> dict:
        """
        提取新闻信号详情
        """
        detail_url = item.get("url", "")
        content = ""

        if detail_url:
            try:
                await self.safe_goto(page, detail_url)
                await self.random_delay()

                # 尝试多种选择器获取正文
                selectors = [
                    "article",
                    ".article-content",
                    ".content",
                    "#content",
                    ".news-content",
                    ".detail-content",
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
            "company_name": item.get("company_name", "未知企业"),
            "title": item.get("title", ""),
            "content": content or item.get("abstract", ""),
            "source_url": detail_url or item.get("url", ""),
            "source_platform": "百度新闻",
            "publish_date": item.get("publish_date", ""),
            "raw_html": None,
        }