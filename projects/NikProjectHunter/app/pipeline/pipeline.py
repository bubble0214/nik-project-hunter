"""
Nik Project Hunter — 数据管道 Pipeline

职责：
1. 数据清洗：清理 HTML 标签、规范化字段
2. 关键词过滤：确保项目与目标方向相关
3. 去重：基于 source_url 检查数据库
4. 存储：写入 PostgreSQL

设计思路：
- Pipeline 是爬虫和数据库之间的中间层
- 每个 Spider 的输出经过 Pipeline 处理后入库
- Pipeline 独立可测试
"""

import datetime
import re
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project


class Pipeline:
    """
    数据管道

    处理流程：
    raw_data -> clean -> keyword_filter -> dedup -> store
    """

    # =============================================================================
    # Data Quality Sprint: 精准行业关键词（仅保留四象限）
    # =============================================================================
    TARGET_KEYWORDS = [
        # 数据治理
        "数据治理", "数据中台", "主数据", "元数据", "数据质量",
        "数据标准", "数据目录", "数据血缘", "数据架构", "数据模型",
        "MDM", "湖仓一体", "Data Fabric", "数据编织",
        "ETL", "ELT", "数据仓库", "数据平台", "数据湖",
        # 数据资产
        "数据资产", "数据要素", "数据运营", "数据共享", "数据流通",
        "数据交易", "数据确权", "数据估值", "数据入表", "数据资本化",
        # AI
        "人工智能", "大模型", "AI平台", "智能分析", "AI中台",
        "机器学习", "LLM", "RAG", "知识库", "知识图谱",
        "智能客服", "Copilot", "NLP", "深度学习",
        "智能决策", "智能风控", "智能营销",
        # 数据安全
        "数据安全", "分类分级", "数据脱敏", "数据风控",
        "隐私计算", "数据合规", "DLP", "零信任",
        # 补充高频词
        "数据驱动", "数据交换", "数据管理", "数据平台",
        "数据服务", "数据分析", "数据接口", "数据集成",
        "数据报送", "数据采集", "数据处理", "数据存储",
        "数据备份", "数据迁移", "数据同步", "数据调度",
        "数据开发", "数据应用", "数据可视化",
        "数据系统", "数据平台", "数据中台",
    ]

    async def process(
        self,
        raw_projects: list[dict],
        source_platform: str,
        session: AsyncSession,
    ) -> dict:
        """
        处理一批原始项目数据

        Args:
            raw_projects: 原始项目数据列表
            source_platform: 来源平台名称
            session: 数据库会话

        Returns:
            {"total": int, "new_count": int, "filtered_count": int, "duplicate_count": int}
        """
        stats = {
            "total": len(raw_projects),
            "cleaned": 0,
            "filtered": 0,
            "duplicates": 0,
            "new": 0,
        }

        for raw in raw_projects:
            # 1. 清洗
            cleaned = self._clean(raw)
            if not cleaned:
                continue
            stats["cleaned"] += 1

            # 2. 关键词过滤
            if not self._keyword_filter(cleaned):
                stats["filtered"] += 1
                continue

            # 3. 去重 + 存储
            success = await self._store(cleaned, session)
            if success:
                stats["new"] += 1
            else:
                stats["duplicates"] += 1

        return {
            "total": stats["total"],
            "new_count": stats["new"],
            "filtered_count": stats["filtered"],
            "duplicate_count": stats["duplicates"],
        }

    # ======================================================================
    # 1. 数据清洗
    # ======================================================================

    def _clean(self, raw: dict) -> Optional[dict]:
        """
        清洗单条项目数据

        清洗内容：
        - 去除 HTML 标签
        - 去除首尾空白
        - 规范化日期格式
        - 规范化预算金额
        """
        try:
            cleaned = {}

            # 标题（必须字段）
            title = raw.get("title", "").strip()
            if not title or len(title) < 5:
                return None
            if re.match(r"^[\d\s\-_./\\()（）\[\]]+$", title):
                return None
            cleaned["title"] = title

            # URL（必须字段）
            source_url = raw.get("source_url", "").strip()
            if not source_url:
                return None
            cleaned["source_url"] = source_url

            # 来源平台
            cleaned["source_platform"] = raw.get("source_platform", "")

            # 发布日期
            publish_date = raw.get("publish_date")
            if isinstance(publish_date, str):
                for fmt in [
                    "%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日",
                    "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M",
                ]:
                    try:
                        publish_date = datetime.datetime.strptime(publish_date, fmt)
                        break
                    except ValueError:
                        continue
            cleaned["publish_date"] = publish_date

            # 地区
            region = raw.get("region")
            if region:
                region = region.strip()
            cleaned["region"] = region

            # 采购单位
            buyer = raw.get("buyer")
            if buyer:
                buyer = buyer.strip()
            cleaned["buyer"] = buyer

            # 预算
            budget = raw.get("budget")
            if budget is not None:
                try:
                    budget = float(budget)
                except (ValueError, TypeError):
                    budget = None
            cleaned["budget"] = budget

            # 正文内容（取前 10000 字符）
            content = raw.get("content", "")
            if content:
                content = re.sub(r"<[^>]+>", "", content)
                content = content.strip()[:10000]
            cleaned["content"] = content

            # 原始 HTML（取前 50000 字符）
            raw_html = raw.get("raw_html", "")
            if raw_html:
                raw_html = raw_html[:50000]
            cleaned["raw_html"] = raw_html

            return cleaned

        except Exception as e:
            logger.warning(f"数据清洗失败: {e}")
            return None

    # ======================================================================
    # 2. 关键词过滤
    # ======================================================================

    def _keyword_filter(self, project: dict) -> bool:
        """
        关键词过滤

        检查标题和正文中是否包含目标关键词
        标题匹配优先（精度更高）
        正文匹配作为补充（召回更多）
        """
        title = project.get("title", "")
        content = project.get("content", "")

        # 标题匹配（高优先级）
        for keyword in self.TARGET_KEYWORDS:
            if keyword.lower() in title.lower():
                return True

        # 正文匹配（低优先级，仅前 500 字符）
        if content:
            content_preview = content[:500]
            for keyword in self.TARGET_KEYWORDS:
                if keyword.lower() in content_preview.lower():
                    return True

        return False

    # ======================================================================
    # 3. 去重 + 存储
    # ======================================================================

    async def _store(self, project_data: dict, session: AsyncSession) -> bool:
        """
        去重后存储到数据库

        Returns:
            True = 新增, False = 已存在
        """
        # 去重检查
        result = await session.execute(
            select(Project).where(Project.source_url == project_data["source_url"])
        )
        if result.scalar_one_or_none():
            return False

        # 创建 Project ORM 对象
        project = Project(
            title=project_data["title"],
            source_url=project_data["source_url"],
            source=project_data.get("source_platform", ""),
            publish_date=project_data.get("publish_date"),
            region=project_data.get("region"),
            buyer=project_data.get("buyer"),
            budget=project_data.get("budget"),
            summary=project_data.get("content", "")[:500] if project_data.get("content") else None,
            raw_html=project_data.get("raw_html"),
            status="new",
        )

        session.add(project)
        return True


# 全局单例
pipeline = Pipeline()