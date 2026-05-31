"""
Nik Project Hunter — 信号 Dashboard API（第五阶段）

职责：
1. 信号列表与过滤
2. 信号采集统计 Dashboard
3. 企业画像查询
4. 战略客户识别
5. 手动触发信号采集
"""

from datetime import datetime, timedelta, timezone
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Query, HTTPException

from app.database import get_db
from app.models import Company, EnterpriseSignal
from app.signals.services.signal_pipeline import signal_pipeline

router = APIRouter(prefix="/api/v1/signals", tags=["signals"])


# =============================================================================
# 辅助函数
# =============================================================================

def _week_range() -> tuple[datetime, datetime]:
    """获取最近 7 天范围"""
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    return now - timedelta(days=7), now


def _month_range() -> tuple[datetime, datetime]:
    """获取最近 30 天范围"""
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    return now - timedelta(days=30), now


# =============================================================================
# API 端点
# =============================================================================


@router.get("")
async def list_signals(
    signal_type: str = Query(None, description="信号类型过滤"),
    company_name: str = Query(None, description="企业名称过滤"),
    status: str = Query(None, description="状态过滤"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    session: AsyncSession = Depends(get_db),
):
    """
    信号列表

    支持按类型、企业、状态过滤。
    """
    try:
        query = select(EnterpriseSignal).order_by(
            EnterpriseSignal.created_at.desc()
        )

        if signal_type:
            query = query.where(EnterpriseSignal.signal_type == signal_type)
        if company_name:
            query = query.where(
                EnterpriseSignal.company_name.ilike(f"%{company_name}%")
            )
        if status:
            query = query.where(EnterpriseSignal.status == status)

        # 总数
        count_query = select(func.count()).select_from(
            query.subquery()
        )
        total = await session.scalar(count_query) or 0

        # 分页
        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        signals = result.scalars().all()

        return {
            "items": [
                {
                    "id": str(s.id),
                    "signal_type": s.signal_type,
                    "company_name": s.company_name,
                    "title": s.title,
                    "source_url": s.source_url,
                    "source_platform": s.source_platform,
                    "publish_date": (
                        s.publish_date.isoformat() if s.publish_date else None
                    ),
                    "signal_score": s.signal_score,
                    "signal_level": s.signal_level,
                    "status": s.status,
                    "analysis_summary": s.analysis_summary,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in signals
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"[信号API] 列表查询异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard")
async def signal_dashboard(
    days: int = Query(7, ge=1, le=90, description="统计天数"),
    session: AsyncSession = Depends(get_db),
):
    """
    信号 Dashboard 统计

    返回：
    1. 本周新增信号
    2. 信号类型分布
    3. AI 建设企业数量
    4. 数据治理建设企业
    5. 高价值企业 TOP10
    6. 政策热点行业
    7. 企业成熟度排行
    """
    try:
        tz = timezone(timedelta(hours=8))
        now = datetime.now(tz)
        range_start = now - timedelta(days=days)

        # 1. 本周新增信号
        total_signals = await session.scalar(
            select(func.count(EnterpriseSignal.id)).where(
                EnterpriseSignal.created_at >= range_start
            )
        ) or 0

        # 2. 信号类型分布
        type_result = await session.execute(
            select(
                EnterpriseSignal.signal_type,
                func.count(EnterpriseSignal.id).label("cnt"),
            )
            .where(EnterpriseSignal.created_at >= range_start)
            .group_by(EnterpriseSignal.signal_type)
        )
        signal_by_type = {row[0]: row[1] for row in type_result}

        # 3. 本周新增信号详细列表（最近 20 条）
        recent_result = await session.execute(
            select(EnterpriseSignal)
            .where(EnterpriseSignal.created_at >= range_start)
            .order_by(EnterpriseSignal.created_at.desc())
            .limit(20)
        )
        recent_signals = [
            {
                "id": str(s.id),
                "signal_type": s.signal_type,
                "company_name": s.company_name,
                "title": s.title[:100],
                "signal_score": s.signal_score,
                "signal_level": s.signal_level,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in recent_result.scalars()
        ]

        # 4. AI 建设企业（AI 成熟度 >= 60）
        ai_companies = await session.scalar(
            select(func.count(Company.id)).where(
                Company.ai_maturity >= 60,
                Company.profile_updated_at >= range_start,
            )
        ) or 0

        # 5. 数据治理建设企业（数据成熟度 >= 60）
        data_companies = await session.scalar(
            select(func.count(Company.id)).where(
                Company.data_maturity >= 60,
                Company.profile_updated_at >= range_start,
            )
        ) or 0

        # 6. 高价值企业 TOP10
        top_result = await session.execute(
            select(Company)
            .where(
                Company.opportunity_score.isnot(None),
                Company.profile_updated_at >= range_start,
            )
            .order_by(Company.opportunity_score.desc())
            .limit(10)
        )
        top_companies = [
            {
                "company_name": c.company_name,
                "industry": c.industry,
                "opportunity_score": c.opportunity_score,
                "strategic_level": c.strategic_level,
                "digital_maturity": c.digital_maturity,
                "ai_maturity": c.ai_maturity,
                "data_maturity": c.data_maturity,
                "recommended_focus": c.recommended_focus,
                "is_strategic": c.is_strategic_customer,
            }
            for c in top_result.scalars()
        ]

        # 7. 企业成熟度排行
        maturity_result = await session.execute(
            select(Company)
            .where(Company.profile_updated_at >= range_start)
            .order_by(
                (
                    func.coalesce(Company.digital_maturity, 0)
                    + func.coalesce(Company.ai_maturity, 0)
                    + func.coalesce(Company.data_maturity, 0)
                ).desc()
            )
            .limit(10)
        )
        maturity_ranking = [
            {
                "company_name": c.company_name,
                "digital_maturity": c.digital_maturity,
                "ai_maturity": c.ai_maturity,
                "data_maturity": c.data_maturity,
                "total_maturity": (c.digital_maturity or 0)
                + (c.ai_maturity or 0)
                + (c.data_maturity or 0),
            }
            for c in maturity_result.scalars()
        ]

        # 8. 战略客户统计
        strategic_count = await session.scalar(
            select(func.count(Company.id)).where(
                Company.strategic_level == "strategic"
            )
        ) or 0

        return {
            "total_signals": total_signals,
            "signal_by_type": signal_by_type,
            "recent_signals": recent_signals,
            "ai_enterprises": ai_companies,
            "data_governance_enterprises": data_companies,
            "top_opportunities": top_companies,
            "maturity_ranking": maturity_ranking,
            "strategic_customer_count": strategic_count,
            "query_range_days": days,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"[信号API] Dashboard 查询异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies")
async def list_companies(
    strategic_only: bool = Query(False, description="仅战略客户"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """
    企业画像列表
    """
    try:
        query = select(Company).order_by(
            Company.opportunity_score.desc().nullslast()
        )

        if strategic_only:
            query = query.where(Company.strategic_level == "strategic")

        # 总数
        count_query = select(func.count()).select_from(query.subquery())
        total = await session.scalar(count_query) or 0

        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        companies = result.scalars().all()

        return {
            "items": [c.profile_summary for c in companies],
            "total": total,
        }

    except Exception as e:
        logger.error(f"[信号API] 企业列表查询异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies/strategic")
async def strategic_companies(
    session: AsyncSession = Depends(get_db),
):
    """
    战略客户列表

    识别标准：
    1. 国企/金融/能源/医疗
    2. 高预算能力
    3. 长期数字化建设
    4. AI 建设趋势明显
    """
    try:
        result = await session.execute(
            select(Company)
            .where(
                Company.strategic_level.in_(["strategic", "high_value"])
            )
            .order_by(Company.opportunity_score.desc().nullslast())
            .limit(20)
        )

        companies = []
        for c in result.scalars():
            profile = c.profile_summary
            profile["latest_signal_summary"] = c.latest_signal_summary
            profile["recommended_strategy"] = c.recommended_strategy
            profile["recommended_department"] = c.recommended_department
            companies.append(profile)

        return {
            "items": companies,
            "total": len(companies),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"[信号API] 战略客户查询异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger")
async def trigger_signal_collection():
    """
    手动触发信号采集

    立即执行一次完整的信号管道（采集 → 分析 → 画像 → 通知）
    """
    try:
        logger.info("[信号API] 手动触发信号采集")
        result = await signal_pipeline.run_pipeline()
        return {
            "status": "completed",
            "result": result,
            "message": "信号采集与分析管道已执行完成",
        }
    except Exception as e:
        logger.error(f"[信号API] 手动触发失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))