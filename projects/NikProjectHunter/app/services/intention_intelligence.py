"""
Nik Project Hunter — 采购意向 Intelligence 引擎（第六阶段）

核心能力：
1. 意向 AI 分析（项目阶段、战略方向、提前介入窗口）
2. 未来商机评分（future_opportunity_score）
3. 意向趋势分析
4. 提前介入 Intelligence 报告
"""

import json
import datetime
import logging
import os
from typing import Optional
from loguru import logger

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProcurementIntention
from app.config import get_settings
from app.core.ai_client import ai_client

settings = get_settings()

# LLM 服务使用 ai_client

# =============================================================================
# 日志
# =============================================================================
INTENTION_LOG_FILE = "logs/intention_intelligence.log"
os.makedirs("logs", exist_ok=True)

intention_logger = logging.getLogger("intention_intelligence")
intention_logger.setLevel(logging.INFO)
if not intention_logger.handlers:
    fh = logging.FileHandler(INTENTION_LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    intention_logger.addHandler(fh)


# =============================================================================
# AI 分析 Prompt
# =============================================================================

INTENTION_ANALYSIS_PROMPT = """你是一个企业级采购意向分析专家。

分析以下采购意向信息，判断：
1. 项目阶段（project_stage）: 规划期 / 预算期 / 立项期 / 招标准备期
2. 战略方向（strategic_direction）: 数据治理 / 数据安全 / 数据资产 / AI智能体 / 大模型 / 数据分类分级 / 其他
3. 预计招标时间（estimated_tender_months）: 从今天算起还有几个月（0-24）
4. 提前介入窗口评分（engagement_window_score）: 0-100，越高越应该立即介入
5. 年度预算信号（annual_budget_signal）: high / medium / low
6. 未来商机评分（future_opportunity_score）: 0-100
7. 推荐销售动作（recommended_action）: 简要描述
8. 推荐跟进部门（recommended_department）: 简要描述
9. 是否属于目标赛道（is_target）: true/false
10. 语义类别（semantic_category）: data_governance / data_security / data_asset / ai / none

采购意向信息：
标题: {title}
采购单位: {buyer}
意向内容: {content}
建设目标: {goal}
技术方向: {technical}
预算描述: {budget}

请以 JSON 格式输出，不要包含其他内容：
{{
    "project_stage": "string",
    "strategic_direction": "string",
    "strategic_directions": ["string"],
    "estimated_tender_months": int,
    "engagement_window_score": int,
    "annual_budget_signal": "string",
    "future_opportunity_score": int,
    "opportunity_level": "strategic / high_value / observation / weak_signal",
    "semantic_category": "string",
    "is_target": true/false,
    "recommended_action": "string",
    "recommended_department": "string",
    "sales_notes": "string",
    "relevance_score": int
}}"""


# =============================================================================
# Intention Intelligence Service
# =============================================================================

class IntentionIntelligenceService:
    """
    采购意向 Intelligence 引擎
    """

    def __init__(self):
        self.ai_client = ai_client
        self.logger = intention_logger

    async def analyze_intention(self, intention: ProcurementIntention) -> dict:
        """
        AI 分析单个采购意向

        返回分析结果并更新 intention 对象。
        """
        # 构建分析内容
        content_parts = []
        if intention.intention_content:
            content_parts.append(intention.intention_content[:2000])
        if intention.annual_plan:
            content_parts.append(f"年度计划: {intention.annual_plan[:500]}")
        if intention.construction_goal:
            content_parts.append(f"建设目标: {intention.construction_goal[:500]}")
        if intention.technical_direction:
            content_parts.append(f"技术方向: {intention.technical_direction[:500]}")
        if intention.budget_description:
            content_parts.append(f"预算: {intention.budget_description[:200]}")

        content = "\n".join(content_parts) if content_parts else intention.title

        prompt = INTENTION_ANALYSIS_PROMPT.format(
            title=intention.title[:200],
            buyer=intention.buyer or "未知",
            content=content[:3000],
            goal=intention.construction_goal or "",
            technical=intention.technical_direction or "",
            budget=intention.budget_description or "",
        )

        try:
            result = await self.ai_client.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(result)

            now = datetime.datetime.now()

            # 计算预计招标日期
            estimated_months = parsed.get("estimated_tender_months", 3)
            estimated_date = now + datetime.timedelta(days=estimated_months * 30)

            # 更新 intention 对象
            intention.project_stage = parsed.get("project_stage", "规划期")
            intention.estimated_tender_date = estimated_date
            intention.engagement_window_score = max(0, min(100, int(parsed.get("engagement_window_score", 50))))
            intention.annual_budget_signal = parsed.get("annual_budget_signal", "medium")
            intention.strategic_direction = parsed.get("strategic_direction", "其他")
            intention.strategic_directions = parsed.get("strategic_directions", [])
            intention.semantic_category = parsed.get("semantic_category", "none")
            intention.semantic_score = max(0, min(100, int(parsed.get("relevance_score", 50))))
            intention.future_opportunity_score = max(0, min(100, int(parsed.get("future_opportunity_score", 50))))
            intention.opportunity_level = parsed.get("opportunity_level", "observation")
            intention.recommended_action = parsed.get("recommended_action", "")[:200]
            intention.recommended_department = parsed.get("recommended_department", "")[:100]
            intention.sales_notes = parsed.get("sales_notes", "")[:300]
            intention.analysis = parsed
            intention.status = "analyzed"

            level = parsed.get("opportunity_level", "observation")
            score = parsed.get("future_opportunity_score", 50)
            self.logger.info(
                f"[Intention] 分析完成 | {intention.title[:50]} | "
                f"stage={parsed.get('project_stage')} | "
                f"direction={parsed.get('strategic_direction')} | "
                f"window={intention.engagement_window_score} | "
                f"future={score} | "
                f"level={level}"
            )

            return {
                "project_stage": intention.project_stage,
                "engagement_window_score": intention.engagement_window_score,
                "future_opportunity_score": intention.future_opportunity_score,
                "opportunity_level": intention.opportunity_level,
                "is_target": parsed.get("is_target", False),
            }

        except json.JSONDecodeError as e:
            logger.warning(f"[IntentionIntelligence] AI 返回非法 JSON: {str(result)[:200]}")
            return self._default_analysis(intention)
        except Exception as e:
            logger.error(f"[IntentionIntelligence] AI 分析异常: {e}")
            return self._default_analysis(intention)

    def _default_analysis(self, intention: ProcurementIntention) -> dict:
        """AI 分析失败时保守默认值"""
        intention.project_stage = "规划期"
        intention.engagement_window_score = 40
        intention.annual_budget_signal = "medium"
        intention.future_opportunity_score = 40
        intention.opportunity_level = "observation"
        intention.status = "analyzed"
        return {
            "project_stage": "规划期",
            "engagement_window_score": 40,
            "future_opportunity_score": 40,
            "opportunity_level": "observation",
            "is_target": False,
        }

    async def analyze_unanalyzed_intentions(self, session: AsyncSession) -> list[dict]:
        """分析所有未分析的采购意向"""
        result = await session.execute(
            select(ProcurementIntention).where(
                ProcurementIntention.status == "new"
            ).order_by(ProcurementIntention.created_at.desc())
        )
        intentions = result.scalars().all()
        if not intentions:
            logger.info("[IntentionIntelligence] 无未分析的采购意向")
            return []

        results = []
        for intention in intentions:
            analysis = await self.analyze_intention(intention)
            results.append(analysis)

        await session.commit()

        logger.info(
            f"[IntentionIntelligence] 分析完成: {len(results)} 个意向 | "
            f"目标赛道: {sum(1 for r in results if r.get('is_target'))} 个"
        )
        return results


# =============================================================================
# 意向 Dashboard 查询
# =============================================================================

class IntentionDashboardService:
    """采购意向 Dashboard 查询服务"""

    @staticmethod
    async def get_overview(session: AsyncSession) -> dict:
        """获取采购意向总览"""
        total = await session.scalar(
            select(func.count(ProcurementIntention.id))
        )
        target_count = await session.scalar(
            select(func.count(ProcurementIntention.id)).where(
                ProcurementIntention.semantic_category.in_(
                    ["data_governance", "data_security", "data_asset", "ai"]
                )
            )
        )
        high_value = await session.scalar(
            select(func.count(ProcurementIntention.id)).where(
                ProcurementIntention.opportunity_level.in_(["strategic", "high_value"])
            )
        )

        # 按项目阶段统计
        stage_result = await session.execute(
            select(
                ProcurementIntention.project_stage,
                func.count(ProcurementIntention.id).label("cnt"),
            ).where(
                ProcurementIntention.project_stage.isnot(None)
            ).group_by(ProcurementIntention.project_stage)
        )
        by_stage = {row[0]: row[1] for row in stage_result}

        # 按方向统计
        direction_result = await session.execute(
            select(
                ProcurementIntention.strategic_direction,
                func.count(ProcurementIntention.id).label("cnt"),
            ).where(
                ProcurementIntention.strategic_direction.isnot(None)
            ).group_by(ProcurementIntention.strategic_direction)
        )
        by_direction = {row[0]: row[1] for row in direction_result}

        # 高价值提前布局项目
        high_value_result = await session.execute(
            select(ProcurementIntention).where(
                ProcurementIntention.opportunity_level.in_(["strategic", "high_value"])
            ).order_by(ProcurementIntention.future_opportunity_score.desc().nullslast())
            .limit(10)
        )
        top_intentions = []
        for i in high_value_result.scalars():
            top_intentions.append({
                "id": str(i.id),
                "title": i.title[:80],
                "buyer": i.buyer,
                "project_stage": i.project_stage,
                "strategic_direction": i.strategic_direction,
                "engagement_window_score": i.engagement_window_score,
                "window_description": i.window_description,
                "future_opportunity_score": i.future_opportunity_score,
                "opportunity_level": i.opportunity_level,
                "estimated_tender_date": i.estimated_tender_date.strftime("%Y-%m") if i.estimated_tender_date else None,
                "recommended_action": i.recommended_action,
                "recommended_department": i.recommended_department,
                "source_url": i.source_url,
            })

        return {
            "total": total or 0,
            "target_count": target_count or 0,
            "high_value_count": high_value or 0,
            "by_stage": by_stage,
            "by_direction": by_direction,
            "top_intentions": top_intentions,
        }

    @staticmethod
    async def get_trends(session: AsyncSession) -> dict:
        """获取意向趋势分析"""
        now = datetime.datetime.now()
        three_months = now - datetime.timedelta(days=90)

        result = await session.execute(
            select(ProcurementIntention).where(
                ProcurementIntention.created_at >= three_months,
                ProcurementIntention.opportunity_level.isnot(None),
            ).order_by(ProcurementIntention.created_at.desc())
        )
        recent = result.scalars().all()

        # 按语义类别统计趋势
        category_trends = {}
        for i in recent:
            cat = i.semantic_category or "none"
            if cat not in category_trends:
                category_trends[cat] = 0
            category_trends[cat] += 1

        # 未来 3-6 月可能招标的项目
        future_window = now + datetime.timedelta(days=180)
        future_result = await session.execute(
            select(ProcurementIntention).where(
                ProcurementIntention.estimated_tender_date.isnot(None),
                ProcurementIntention.estimated_tender_date <= future_window,
                ProcurementIntention.estimated_tender_date >= now,
                ProcurementIntention.semantic_category.in_(
                    ["data_governance", "data_security", "data_asset", "ai"]
                ),
            ).order_by(ProcurementIntention.estimated_tender_date.asc())
        )
        upcoming = []
        for i in future_result.scalars():
            upcoming.append({
                "title": i.title[:80],
                "buyer": i.buyer,
                "estimated_tender_date": i.estimated_tender_date.strftime("%Y-%m-%d") if i.estimated_tender_date else None,
                "strategic_direction": i.strategic_direction,
                "future_opportunity_score": i.future_opportunity_score,
                "opportunity_level": i.opportunity_level,
            })

        return {
            "category_trends": category_trends,
            "upcoming_projects_3_6_months": upcoming,
            "total_recent_90d": len(recent),
        }

    @staticmethod
    async def get_high_value_early_layout(session: AsyncSession) -> list[dict]:
        """获取高价值提前布局项目"""
        result = await session.execute(
            select(ProcurementIntention).where(
                ProcurementIntention.opportunity_level.in_(["strategic", "high_value"]),
                ProcurementIntention.engagement_window_score >= 60,
            ).order_by(
                ProcurementIntention.engagement_window_score.desc().nullslast()
            ).limit(15)
        )
        items = []
        for i in result.scalars():
            items.append({
                "id": str(i.id),
                "title": i.title,
                "buyer": i.buyer,
                "region": i.region,
                "project_stage": i.project_stage,
                "strategic_direction": i.strategic_direction,
                "engagement_window_score": i.engagement_window_score,
                "window_description": i.window_description,
                "estimated_tender_date": i.estimated_tender_date.strftime("%Y-%m") if i.estimated_tender_date else None,
                "future_opportunity_score": i.future_opportunity_score,
                "opportunity_level": i.opportunity_level,
                "recommended_action": i.recommended_action,
                "recommended_department": i.recommended_department,
                "source_url": i.source_url,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            })
        return items


# =============================================================================
# 全局单例
# =============================================================================

intention_intelligence_service = IntentionIntelligenceService()
intention_dashboard_service = IntentionDashboardService()