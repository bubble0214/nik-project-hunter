"""
Nik Project Hunter — Dashboard Intelligence API（第四阶段）

职责：
1. 战略级项目识别与统计
2. TOP10 高价值跟进列表
3. 行业价值分布统计
4. 长期/连续性项目统计
5. AI 与数据资产化项目趋势
6. 商机 Intelligence 总览

原则：
- 单表查询，不做多表 JOIN
- 所有数据从 projects 表聚合
- Intelligence 字段优先
"""

import json
from datetime import datetime, timedelta, timezone
from loguru import logger
from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Query

from app.database import get_db as get_session
from app.models import Project
from app.config import get_settings

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
settings = get_settings()


def _today_range() -> tuple[datetime, datetime]:
    """获取今日 0 点 - 24 点范围"""
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(hours=24)
    return today_start, today_end


def _week_range() -> tuple[datetime, datetime]:
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    week_start = now - timedelta(days=7)
    return week_start, now


def _month_range() -> tuple[datetime, datetime]:
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    month_start = now - timedelta(days=30)
    return month_start, now


def _intelligence_summary(project: Project) -> dict:
    """提取项目的 Intelligence 摘要"""
    return {
        "customer_maturity": project.customer_maturity_score,
        "long_term_value": project.long_term_value_score,
        "industry_value": project.industry_value_score,
        "bidding_probability": project.bidding_probability_score,
        "business_difficulty": project.business_difficulty_score,
        "opportunity_level": project.opportunity_level,
    }


@router.get("/stats")
async def get_stats(session: AsyncSession = Depends(get_session)):
    """
    Dashboard 基础统计（Phase 3）

    返回：今日新增、各等级数量、来源分布、地区分布、最近高价值
    """
    try:
        today_start, today_end = _today_range()

        # 今日新增
        today_count = await session.scalar(
            select(func.count(Project.id)).where(
                Project.created_at >= today_start,
                Project.created_at < today_end,
            )
        )

        # 等级统计
        grade_counts = {}
        for grade in ["S", "A", "B", "C"]:
            cnt = await session.scalar(
                select(func.count(Project.id)).where(Project.score_grade == grade)
            )
            grade_counts[grade] = cnt or 0

        # 来源分布
        source_result = await session.execute(
            select(Project.source, func.count(Project.id).label("cnt"))
            .group_by(Project.source)
            .order_by(func.count(Project.id).desc())
        )
        by_source = [{"source": row[0], "count": row[1]} for row in source_result]

        # 地区分布
        region_result = await session.execute(
            select(Project.region, func.count(Project.id).label("cnt"))
            .where(Project.region.isnot(None))
            .group_by(Project.region)
            .order_by(func.count(Project.id).desc())
            .limit(10)
        )
        by_region = [{"region": row[0], "count": row[1]} for row in region_result]

        # 最近高价值 TOP10
        high_value_result = await session.execute(
            select(Project)
            .where(Project.score.isnot(None))
            .order_by(Project.score.desc())
            .limit(10)
        )
        recent_high = [
            {
                "id": str(p.id),
                "title": p.title,
                "score": p.score,
                "score_grade": p.score_grade,
                "buyer": p.buyer,
                "budget": p.budget,
                "source": p.source,
                "publish_date": (
                    p.publish_date.isoformat() if p.publish_date else None
                ),
                "opportunity_level": p.opportunity_level,
            }
            for p in high_value_result.scalars()
        ]

        return {
            "today_new": today_count or 0,
            "total": await session.scalar(select(func.count(Project.id))),
            "grade_counts": grade_counts,
            "by_source": by_source,
            "by_region": by_region,
            "recent_high_value": recent_high,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"[Dashboard] 统计查询异常: {e}")
        return {"error": str(e)}


@router.get("/intelligence")
async def get_intelligence(
    days: int = Query(30, ge=1, le=365, description="统计天数范围"),
    session: AsyncSession = Depends(get_session),
):
    """
    Dashboard Intelligence API（第四阶段新增）

    返回商机 Intelligence 增强统计：
    1. 战略级项目统计
    2. TOP10 最值得跟进项目
    3. 高价值行业分布
    4. 长期项目统计
    5. AI 与数据资产化项目趋势
    6. 商机 Intelligence 总览
    """
    try:
        tz = timezone(timedelta(hours=8))
        now = datetime.now(tz)
        range_start = now - timedelta(days=days)

        # 1. 战略级项目
        strategic_result = await session.execute(
            select(Project)
            .where(
                Project.opportunity_level == "strategic",
                Project.created_at >= range_start,
            )
            .order_by(Project.score.desc().nullslast())
        )
        strategic_projects = []
        for p in strategic_result.scalars():
            budget_display = (
                f"{p.budget / 10000:.0f}万" if p.budget else "未知"
            )
            strategic_projects.append(
                {
                    "id": str(p.id),
                    "title": p.title,
                    "buyer": p.buyer,
                    "budget": p.budget,
                    "budget_display": budget_display,
                    "score": p.score,
                    "score_grade": p.score_grade,
                    "opportunity_level": p.opportunity_level,
                    "customer_maturity": p.customer_maturity_score,
                    "bidding_probability": p.bidding_probability_score,
                    "source_url": p.source_url,
                    "created_at": (
                        p.created_at.isoformat() if p.created_at else None
                    ),
                }
            )

        # 2. TOP10 最值得跟进
        top_result = await session.execute(
            select(Project)
            .where(
                Project.score_grade.in_(["S", "A"]),
                Project.score.isnot(None),
            )
            .order_by(Project.score.desc())
            .limit(10)
        )
        top_follow = []
        for p in top_result.scalars():
            analysis = p.analysis if isinstance(p.analysis, dict) else {}
            intelligence = analysis.get("opportunity_intelligence", {})
            sales_strategy = intelligence.get("sales_strategy", {})

            top_follow.append(
                {
                    "id": str(p.id),
                    "title": p.title,
                    "buyer": p.buyer,
                    "budget": p.budget,
                    "score": p.score,
                    "score_grade": p.score_grade,
                    "opportunity_level": p.opportunity_level,
                    "customer_maturity": p.customer_maturity_score,
                    "bidding_probability": p.bidding_probability_score,
                    "long_term_value": p.long_term_value_score,
                    "sales_strategy": {
                        "contact_department": sales_strategy.get(
                            "contact_department", ""
                        ),
                        "entry_point": sales_strategy.get("entry_point", ""),
                        "main_focus": sales_strategy.get("main_focus", ""),
                        "approach_type": sales_strategy.get(
                            "approach_type", ""
                        ),
                    },
                    "source_url": p.source_url,
                }
            )

        # 3. 高价值行业分布
        industry_result = await session.execute(
            select(
                Project.opportunity_level,
                func.count(Project.id).label("cnt"),
            )
            .where(
                Project.opportunity_level.isnot(None),
                Project.created_at >= range_start,
            )
            .group_by(Project.opportunity_level)
        )
        opportunity_levels = {
            row[0]: row[1] for row in industry_result
        }

        # 统计行业（从 analysis JSON 中提取）
        industry_counts = {}
        industry_query = await session.execute(
            select(Project.analysis)
            .where(
                Project.analysis.isnot(None),
                Project.created_at >= range_start,
            )
        )
        for row in industry_query:
            analysis = row[0]
            if isinstance(analysis, dict):
                ind = analysis.get("industry_type", "其他")
                industry_counts[ind] = industry_counts.get(ind, 0) + 1

        industry_distribution = sorted(
            [{"industry": k, "count": v} for k, v in industry_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )

        # 4. 长期项目统计
        long_track_count = await session.scalar(
            select(func.count(Project.id))
            .where(
                Project.opportunity_level == "strategic",
                Project.long_term_value_score >= 70,
                Project.created_at >= range_start,
            )
        )

        long_track_result = await session.execute(
            select(Project)
            .where(
                Project.long_term_value_score >= 70,
                Project.created_at >= range_start,
            )
            .order_by(Project.long_term_value_score.desc())
            .limit(10)
        )
        long_track_projects = [
            {
                "id": str(p.id),
                "title": p.title,
                "buyer": p.buyer,
                "long_term_value_score": p.long_term_value_score,
                "customer_maturity_score": p.customer_maturity_score,
                "score": p.score,
                "score_grade": p.score_grade,
            }
            for p in long_track_result.scalars()
        ]

        # 5. AI 与数据资产化项目
        ai_data_asset_counts = {"ai_project": 0, "data_asset": 0, "data_governance": 0, "both": 0}
        analysis_query = await session.execute(
            select(Project.analysis)
            .where(
                Project.analysis.isnot(None),
                Project.created_at >= range_start,
            )
        )
        for row in analysis_query:
            analysis = row[0]
            if isinstance(analysis, dict):
                is_ai = analysis.get("is_ai_project", False)
                is_da = analysis.get("is_data_asset", False)
                is_dg = analysis.get("is_data_governance", False)
                if is_ai:
                    ai_data_asset_counts["ai_project"] += 1
                if is_da:
                    ai_data_asset_counts["data_asset"] += 1
                if is_dg:
                    ai_data_asset_counts["data_governance"] += 1
                if is_ai and is_da:
                    ai_data_asset_counts["both"] += 1

        # 6. Intelligence 总览
        avg_query = await session.execute(
            select(
                func.avg(Project.customer_maturity_score),
                func.avg(Project.long_term_value_score),
                func.avg(Project.industry_value_score),
                func.avg(Project.bidding_probability_score),
                func.avg(Project.business_difficulty_score),
            ).where(
                Project.created_at >= range_start,
            )
        )
        avg_row = avg_query.one()
        intelligence_overview = {
            "avg_customer_maturity": round(avg_row[0] or 0, 1),
            "avg_long_term_value": round(avg_row[1] or 0, 1),
            "avg_industry_value": round(avg_row[2] or 0, 1),
            "avg_bidding_probability": round(avg_row[3] or 0, 1),
            "avg_business_difficulty": round(avg_row[4] or 0, 1),
            "opportunity_level_distribution": opportunity_levels,
            "total_projects_in_range": (
                await session.scalar(
                    select(func.count(Project.id)).where(
                        Project.created_at >= range_start
                    )
                )
                or 0
            ),
        }

        return {
            "strategic_projects": {
                "count": len(strategic_projects),
                "projects": strategic_projects,
            },
            "top_follow_up": top_follow,
            "industry_distribution": industry_distribution,
            "long_track": {
                "count": long_track_count or 0,
                "projects": long_track_projects,
            },
            "ai_data_asset_trends": ai_data_asset_counts,
            "intelligence_overview": intelligence_overview,
            "query_range_days": days,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"[Dashboard] Intelligence 查询异常: {e}")
        return {"error": str(e)}


@router.get("/observation")
async def get_observation(
    include_report: bool = Query(False, description="是否包含 AI Intelligence Report"),
    session: AsyncSession = Depends(get_session),
):
    """
    Observation Dashboard API（Intelligence Observation Sprint 新增）

    返回:
    - crawl_stats: 每日抓取统计
    - keyword_effectiveness: 关键词效果统计
    - industry_heatmap: 行业热度统计
    - project_type_stats: 项目类型统计
    - high_value_stats: 高价值项目统计
    - trend_intelligence: 趋势分析
    - daily_report: (可选) AI Intelligence Report
    """
    try:
        from app.services.observation import (
            get_observation_dashboard,
            generate_daily_intelligence_report,
        )

        dashboard_data = await get_observation_dashboard(session)

        result = {
            "crawl_stats": dashboard_data["crawl_stats"],
            "keyword_effectiveness": dashboard_data["keyword_effectiveness"],
            "industry_heatmap": dashboard_data["industry_heatmap"],
            "project_type_stats": dashboard_data["project_type_stats"],
            "high_value_stats": dashboard_data["high_value_stats"],
            "trend_intelligence": dashboard_data["trend_intelligence"],
            "updated_at": dashboard_data["updated_at"],
        }

        if include_report:
            report = await generate_daily_intelligence_report(session)
            result["daily_report"] = report

        return result

    except Exception as e:
        logger.error(f"[Dashboard] Observation 查询异常: {e}")
        return {"error": str(e)}


@router.get("/spider-health")
async def get_spider_health(
    session: AsyncSession = Depends(get_session),
):
    """
    Spider Health Intelligence API（Intelligence Sprint 新增）

    返回:
    - 各 Spider 成功率
    - 被封率
    - Intelligence 质量
    - 数据贡献度
    - 趋势分析
    """
    try:
        from app.services.spider_health import (
            get_spider_health_from_db,
            analyze_trends,
        )

        health_data = await get_spider_health_from_db(session)
        trends = await analyze_trends(session)

        return {
            "spider_health": health_data,
            "trend_intelligence": trends,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"[Dashboard] Spider Health 查询异常: {e}")
        return {"error": str(e)}


@router.get("/observation/report")
async def get_observation_report(
    report_type: str = Query("daily", pattern="^(daily|weekly)$", description="报告类型"),
    session: AsyncSession = Depends(get_session),
):
    """
    获取 Intelligence Report（每日或每周）

    - report_type=daily: 今日 Intelligence Report
    - report_type=weekly: 本周 Intelligence Summary
    """
    try:
        from app.services.observation import (
            generate_daily_intelligence_report,
            generate_weekly_intelligence_report,
        )

        if report_type == "weekly":
            report = await generate_weekly_intelligence_report(session)
        else:
            report = await generate_daily_intelligence_report(session)

        return report

    except Exception as e:
        logger.error(f"[Dashboard] Observation Report 查询异常: {e}")
        return {"error": str(e)}


@router.get("/intention")
async def get_intention_intelligence(
    include_trends: bool = Query(False, description="是否包含趋势分析"),
    session: AsyncSession = Depends(get_session),
):
    """
    采购意向 Intelligence Dashboard（第六阶段新增）

    返回:
    - overview: 采购意向总览
    - high_value_early_layout: 高价值提前布局项目
    - trends: (可选) 意向趋势分析
    """
    try:
        from app.services.intention_intelligence import intention_dashboard_service

        overview = await intention_dashboard_service.get_overview(session)
        early_layout = await intention_dashboard_service.get_high_value_early_layout(session)

        result = {
            "overview": overview,
            "high_value_early_layout": early_layout,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if include_trends:
            trends = await intention_dashboard_service.get_trends(session)
            result["trends"] = trends

        return result

    except Exception as e:
        logger.error(f"[Dashboard] Intention Intelligence 查询异常: {e}")
        return {"error": str(e)}