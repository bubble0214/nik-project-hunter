"""
Nik Project Hunter — 招聘信号爬虫（第五阶段）

监听维度：
- 数据治理工程师/架构师
- 数据中台工程师
- AI / 大模型工程师
- 数据资产管理员
- 数据安全工程师

来源：Boss直聘 / 猎聘 / 拉勾（通过搜索引擎聚合）
"""

import re
from datetime import datetime
from loguru import logger
from playwright.async_api import Page

from app.signals.spiders.base import SignalSpiderBase


class RecruitmentSignalSpider(SignalSpiderBase):
    """
    招聘信号爬虫

    监听目标企业的人才招聘动态，分析企业数字化/AI 建设意向。
    """

    name = "recruitment_signal"
    signal_type = "recruitment"
    signal_source = "招聘平台"

    # 数据治理/AI/数据资产相关岗位关键词
    TARGET_JOB_KEYWORDS = [
        "数据治理", "数据中台", "主数据", "元数据",
        "数据架构师", "数据工程师", "数据质量",
        "AI", "人工智能", "大模型", "LLM", "RAG",
        "数据资产", "数据运营", "数据产品",
        "数据安全", "数据合规", "数据隐私",
        "数字化", "数字化转型", "大数据",
        "知识图谱", "智能客服", "NLP",
    ]

    # 目标企业名单（从项目库中持续积累）
    TARGET_COMPANIES = [
        "中国移动", "中国联通", "中国电信",
        "中国银行", "工商银行", "建设银行", "农业银行",
        "国家电网", "南方电网",
        "中国石油", "中国石化",
        "华为", "腾讯", "阿里", "百度",
        # 更多企业通过搜索引擎动态发现
    ]

    search_url = "https://www.zhipin.com/web/geek/job?query=数据治理&city=100010000"

    async def parse_signals(self, page: Page) -> list[dict]:
        """
        解析 Boss直聘 搜索列表页

        提取岗位信息：
        - 公司名称
        - 岗位标题
        - 发布日期
        """
        signals = []
        try:
            # 等待列表加载
            await page.wait_for_selector(".job-list-box", timeout=15000)

            # 提取岗位卡片
            job_cards = await page.query_selector_all(".job-card-wrapper")
            for card in job_cards[:20]:  # 每页最多 20 个
                try:
                    title_el = await card.query_selector(".job-name")
                    company_el = await card.query_selector(".company-name")
                    link_el = await card.query_selector("a.job-card-left")
                    date_el = await card.query_selector(".job-time")

                    title = await title_el.inner_text() if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    url = await link_el.get_attribute("href") if link_el else ""
                    date_text = await date_el.inner_text() if date_el else ""

                    title = title.strip()
                    company = company.strip()

                    # 过滤：只保留目标岗位
                    if not any(kw.lower() in title.lower() for kw in self.TARGET_JOB_KEYWORDS):
                        continue

                    # 补齐 URL
                    if url and not url.startswith("http"):
                        url = f"https://www.zhipin.com{url}"

                    signals.append({
                        "title": title,
                        "company_name": company,
                        "url": url,
                        "publish_date": date_text.strip(),
                    })

                except Exception as e:
                    logger.debug(f"[招聘信号] 解析卡片失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"[招聘信号] 列表页解析失败: {e}")

        return signals

    async def extract_signal_detail(self, page: Page, item: dict) -> dict:
        """
        提取招聘信号详情

        分析：
        - 岗位要求（技能栈）
        - 是否与数据治理/AI/数据资产相关
        - 岗位级别（是否高级/管理岗 = 企业认真投入）
        """
        detail_url = item.get("url", "")
        if detail_url:
            await self.safe_goto(page, detail_url)
            await self.random_delay()

        content = ""
        try:
            # 提取岗位描述
            desc_el = await page.query_selector(".job-detail-section .job-sec-text")
            if desc_el:
                content = await desc_el.inner_text()
                content = content.strip()[:2000]
        except Exception:
            pass

        return {
            "signal_type": self.signal_type,
            "company_name": item.get("company_name", "未知企业"),
            "title": item.get("title", ""),
            "content": content or f"岗位: {item.get('title', '')} | 公司: {item.get('company_name', '')}",
            "source_url": detail_url or item.get("url", ""),
            "source_platform": "Boss直聘",
            "publish_date": item.get("publish_date", ""),
            "raw_html": None,
        }


# =============================================================================
# 备用爬虫：通过搜索引擎聚合招聘信息
# =============================================================================

class RecruitmentSignalSpiderSearch(RecruitmentSignalSpider):
    """
    通过搜索引擎采集招聘信号

    搜索关键词组合：
    - 数据治理 招聘
    - AI 大模型 招聘
    - 数据资产 招聘
    """

    name = "recruitment_signal_search"

    search_url = "https://www.baidu.com/s?wd=数据治理 招聘 AI 大模型&rn=20"

    async def parse_signals(self, page: Page) -> list[dict]:
        """
        解析百度搜索结果中的招聘信息
        """
        signals = []
        try:
            await page.wait_for_selector("#content_left", timeout=15000)
            results = await page.query_selector_all(".result")

            for result in results[:15]:
                try:
                    title_el = await result.query_selector("h3 a")
                    abstract_el = await result.query_selector(".c-abstract")

                    title = await title_el.inner_text() if title_el else ""
                    url = await title_el.get_attribute("href") if title_el else ""
                    abstract = await abstract_el.inner_text() if abstract_el else ""

                    title = title.strip()
                    abstract = abstract.strip()

                    # 识别公司名（从标题或摘要中提取）
                    company_name = "未知企业"
                    # 常见的招聘标题模式: "【公司名】招聘XXX"
                    company_match = re.search(r'【(.+?)】', title)
                    if company_match:
                        company_name = company_match.group(1)
                    else:
                        company_match = re.search(r'(.+?)招聘', title)
                        if company_match:
                            company_name = company_match.group(1).strip()

                    signals.append({
                        "title": title,
                        "company_name": company_name,
                        "url": url,
                        "publish_date": "",
                        "abstract": abstract,
                    })

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"[招聘信号-搜索] 解析失败: {e}")

        return signals

    async def extract_signal_detail(self, page: Page, item: dict) -> dict:
        return {
            "signal_type": self.signal_type,
            "company_name": item.get("company_name", "未知企业"),
            "title": item.get("title", ""),
            "content": item.get("abstract", item.get("title", "")),
            "source_url": item.get("url", ""),
            "source_platform": "搜索引擎",
            "publish_date": item.get("publish_date", ""),
            "raw_html": None,
        }