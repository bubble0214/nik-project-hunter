"""
Nik Project Hunter — 采购意向爬虫基类（第六阶段）

所有采购意向爬虫继承此基类。
核心方法：crawl_intents() — 返回意向列表给 manager
"""

import re
import random
import datetime
from typing import Optional
import asyncio

import httpx
from bs4 import BeautifulSoup
from loguru import logger


class ProcurementIntentionSpider:
    """
    采购意向爬虫基类

    所有意向爬虫必须实现 crawl_intents() 方法。
    """

    name: str = ""
    source_platform: str = ""
    base_url: str = ""

    min_delay: float = 3.0
    max_delay: float = 8.0
    max_retries: int = 3

    def __init__(self):
        self._http_client = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Connection": "keep-alive",
                },
            )
        return self._http_client

    async def random_delay(self):
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)

    async def crawl_intents(self) -> list[dict]:
        """
        所有子类必须实现此方法

        Returns:
            list[dict]: 每个 dict 包含:
                - title: 意向标题
                - source_url: 来源 URL
                - publish_date: 发布日期 (可选)
                - buyer: 采购单位 (可选)
                - region: 地区 (可选)
                - estimated_budget: 估算预算 (float, 可选)
                - intention_content: 意向详细内容
                - annual_plan: 年度计划内容 (可选)
                - construction_goal: 建设目标 (可选)
                - technical_direction: 技术方向 (可选)
                - budget_description: 预算描述 (可选)
        """
        raise NotImplementedError

    def _parse_budget(self, text: str) -> Optional[float]:
        """从文本中提取预算金额"""
        patterns = [
            r"(?:预算金额|项目预算|预算|投资金额|采购预算)[：:]\s*([\d,]+(?:\.\d+)?)\s*万?元?",
            r"(?:预算|总投资)[约]?([\d,]+(?:\.\d+)?)\s*万?元?",
            r"([\d,]+(?:\.\d+)?)\s*万元[左右]?",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                try:
                    amount = float(m.group(1).replace(",", ""))
                    if "万" in text[max(0, m.start()-10):m.end()+10]:
                        amount *= 10000
                    return amount
                except ValueError:
                    pass
        return None

    def _parse_region(self, title: str, content: str = "") -> str:
        """从标题/内容中提取地区"""
        combined = title + " " + content
        regions = ["北京", "上海", "广东", "浙江", "江苏", "深圳", "天津",
                    "重庆", "四川", "湖北", "山东", "福建", "湖南", "河南",
                    "安徽", "河北", "陕西", "辽宁", "江西", "云南", "广西",
                    "山西", "贵州", "甘肃", "海南", "内蒙古", "新疆", "宁夏",
                    "青海", "西藏", "黑龙江", "吉林"]
        for r in regions:
            if r in combined:
                return r
        return ""