"""
Nik Project Hunter — Sales Dashboard API（第六阶段）

AI 销售 Dashboard 端点：

GET /api/v1/dashboard/sales
输出：
1. 最值得跟进项目（immediate 优先级）
2. 本周推荐行动（this_week 优先级）
3. 高优先级客户 TOP10
4. 长周期项目列表
5. 高风险项目列表
6. AI 销售建议汇总
"""

from datetime import datetime, timezone, timedelta
from loguru import logger
from sqlalchemy import func, select, desc, case
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Query, HTTPException

from app.database import get_db
from app.models import Project, Company
from app.sales.models import SalesOpportunity
from app.sales.services.sales_service import sales_service

router = APIRouter(prefix="/api/v1/dashboard", tags=["sales_dashboard"])


# =============================================================================
# 辅助函数
# =============================================================================

def _format_sales_opp(opp: SalesOpportunity) -> dict:
    """格式化销售商机"""
    return {
        "id": str(opp.id),
        "company_name": opp.company_name,
        "project_id": str(opp.project_id) if opp.project_id else None,
        "company_id": str(opp.company_id) if opp.company_id else None,
        "sales_stage": opp.sales_stage,
        "stage_display": opp.stage_display,
        "best_entry_department": opp.best_entry_department,
        "recommended_sales_path": opp.recommended_sales_path,
        "recommended_pitch": opp.recommended_pitch,
        "recommended_solution": opp.recommended_solution,
        "recommended_strategy": opp.recommended_strategy,
        "project_priority": opp.project_priority,
        "priority_display": opp.priority_display,
        "recommended_action": opp.recommended_action,
        "relationship_risk": opp.relationship_risk,
        "risk_display": opp.risk_display,
        "next_followup_at": (
            opp.next_followup_at.isoformat() if opp.next_followup_at else None
        ),
        "ai_sales_summary": opp.ai_sales_summary,
        "created_at": opp.created_at.isoformat() if opp.created_at else None,
        "updated_at": opp.updated_at.isoformat() if opp.updated_at else None,
    }


def _enrich_with_project(opp: SalesOpportunity, projects: dict) -> dict:
    """补充项目信息"""
    result = _format_sales_opp(opp)
    if opp.project_id and opp.project_id in projects:
        proj = projects[opp.project_id]
        result["project"] = {
            "title": proj.title,
            "buyer": proj.buyer,
            "budget": proj.budget,
            "region": proj.region,
            "score": proj.score,
            "score_grade": proj.score_grade,
            "source_url": proj.source_url,
        }
    return result


def _enrich_with_company(opp: SalesOpportunity, companies: dict) -> dict:
    """补充企业信息"""
    result = _format_sales_opp(opp)
    if opp.company_id and opp.company_id in companies:
        comp = companies[opp.company_id]
        result["company"] = {
            "industry": comp.industry,
            "digital_maturity": comp.digital_maturity,
            "ai_maturity": comp.ai_maturity,
            "data_maturity": comp.data_maturity,
            "opportunity_score": comp.opportunity_score,
            "strategic_level": comp.strategic_level,
        }
    return result


# =============================================================================
# Dashboard API 端点
# =============================================================================


@router.get("/sales")
async def sales_dashboard(
    session: AsyncSession = Depends(get_db),
):
    """
    销售 Dashboard

    返回 AI 销售副驾驶系统核心数据：
    1. 最值得跟进项目（immediate 优先级）
    2. 本周推荐行动（this_week 优先级）
    3. 高优先级客户 TOP10
    4. 长周期项目列表
    5. 高风险项目列表
    6. AI 销售建议汇总
    """
    try:
        now = datetime.now(timezone.utc)

        # ------------------------------------------------------------------
        # 1. 最值得跟进项目（immediate 优先级）
        # ------------------------------------------------------------------
        immediate_result = await session.execute(
            select(SalesOpportunity)
            .where(SalesOpportunity.project_priority == "immediate")
            .order_by(SalesOpportunity.updated_at.desc())
            .limit(10)
        )
        immediate_opps = immediate_result.scalars().all()

        # ------------------------------------------------------------------
        # 2. 本周推荐行动（this_week 优先级）
        # ------------------------------------------------------------------
        week_result = await session.execute(
            select(SalesOpportunity)
            .where(SalesOpportunity.project_priority == "this_week")
            .order_by(SalesOpportunity.updated_at.desc())
            .limit(10)
        )
        week_opps = week_result.scalars().all()

        # ------------------------------------------------------------------
        # 3. 高优先级客户 TOP10（综合评分最高的）
        # ------------------------------------------------------------------
        top_result = await session.execute(
            select(SalesOpportunity)
            .order_by(
                case(
                    (SalesOpportunity.project_priority == "immediate", 0),
                    (SalesOpportunity.project_priority == "this_week", 1),
                    (SalesOpportunity.project_priority == "long_term", 2),
                    else_=3,
                ),
                SalesOpportunity.updated_at.desc(),
            )
            .limit(10)
        )
        toptop_opps = top_result.scalars().all()

        # ------------------------------------------------------------------
        # 4. 长周期项目列表
        # ------------------------------------------------------------------
        long_term_result = await session.execute(
            select(SalesOpportunity)
            .where(SalesOpportunity.project_priority == "long_term")
            .order_by(SalesOpportunity.updated_at.desc())
            .limit(20)
        )
        long_term_opps = long_term_result.scalars().all()

        # ------------------------------------------------------------------
        # 5. 高风险项目列表
        # ------------------------------------------------------------------
        high_risk_opps = await sales_service.get_high_risk_opportunities(session, limit=20)

        # ------------------------------------------------------------------
        # 6. AI 销售建议汇总
        # ------------------------------------------------------------------
        summary = await _generate_sales_summary(
            session, immediate_opps, week_opps, high_risk_opps
        )

        # ------------------------------------------------------------------
        # 补充项目/企业信息
        # ------------------------------------------------------------------
        # 收集所有 project_id 和 company_id
        all_opps = immediate_opps + week_opps + long_term_opps + high_risk_opps
        project_ids = list(set(o.project_id for o in all_opps if o.project_id))
        company_ids = list(set(o.company_id for o in all_opps if o.company_id))

        # 批量查询
        projects = {}
        if project_ids:
            proj_result = await session.execute(
                select(Project).where(Project.id.in_(project_ids))
            )
            for p in proj_result.scalars():
                projects[p.id] = p

        companies = {}
        if company_ids:
            comp_result = await session.execute(
                select(Company).where(Company.id.in_(company_ids))
            )
            for c in comp_result.scalars():
                companies[c.id] = c

        # 格式化输出
        return {
            "immediate_followup": [
                _enrich_with_project(o, projects) for o in immediate_opps
            ],
            "weekly_actions": [
                _enrich_with_project(o, projects) for o in week_opps
            ],
            "top_priority_customers": [
                _enrich_with_company(o, companies) for o in toptop_opps
            ],
            "long_term_projects": [
                _enrich_with_project(o, projects) for o in long_term_opps
            ],
            "high_risk_projects": [
                _enrich_with_project(o, projects) for o in high_risk_opps
            ],
            "ai_sales_summary": summary,
            "stats": {
                "immediate_count": len(immediate_opps),
                "weekly_count": len(week_opps),
                "long_term_count": len(long_term_opps),
                "high_risk_count": len(high_risk_opps),
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"[销售Dashboard] 查询异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 辅助 API 端点
# =============================================================================


@router.get("/sales/opportunities")
async def list_sales_opportunities(
    priority: str = Query(None, description="按优先级过滤"),
    stage: str = Query(None, description="按销售阶段过滤"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """
    销售商机列表

    支持按优先级、销售阶段过滤。
    """
    try:
        query = select(SalesOpportunity).order_by(
            case(
                (SalesOpportunity.project_priority == "immediate", 0),
                (SalesOpportunity.project_priority == "this_week", 1),
                (SalesOpportunity.project_priority == "long_term", 2),
                else_=3,
            ),
            SalesOpportunity.updated_at.desc(),
        )

        if priority:
            query = query.where(SalesOpportunity.project_priority == priority)
        if stage:
            query = query.where(SalesOpportunity.sales_stage == stage)

        # 总数
        count_query = select(func.count()).select_from(query.subquery())
        total = await session.scalar(count_query) or 0

        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        opps = result.scalars().all()

        return {
            "items": [_format_sales_opp(o) for o in opps],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"[销售API] 商机列表查询异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sales/analyze")
async def trigger_sales_analysis(
    company_name: str = Query(None, description="指定企业名称"),
    session: AsyncSession = Depends(get_db),
):
    """
    手动触发销售分析

    可指定企业名称，或分析所有未分析的商机。
    """
    try:
        if company_name:
            # 分析指定企业
            opp = await sales_service.analyze_opportunity(
                session=session, company_name=company_name
            )
            return {
                "status": "completed",
                "item": _format_sales_opp(opp),
                "message": f"销售分析完成: {company_name}",
            }
        else:
            # 分析所有项目
            results = await sales_service.analyze_all_projects(session, limit=50)
            return {
                "status": "completed",
                "count": len(results),
                "message": f"批量销售分析完成: {len(results)} 个",
            }

    except Exception as e:
        logger.error(f"[销售API] 触发分析异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 内部辅助
# =============================================================================

async def _generate_sales_summary(
    session: AsyncSession,
    immediate_opps: list,
    week_opps: list,
    high_risk_opps: list,
) -> str:
    """生成 AI 销售建议汇总"""
    try:
        immediate_names = [o.company_name for o in immediate_opps[:5]]
        week_names = [o.company_name for o in week_opps[:5]]
        risk_names = [o.company_name for o in high_risk_opps[:5]]

        from app.core.ai_client import ai_client

        prompt = (
            f"请为销售团队生成一个简洁的 AI 销售建议汇总（50-100字）：\n\n"
            f"立即跟进客户（{len(immediate_opps)} 个）: {', '.join(immediate_names)}\n"
            f"本周推荐跟进（{len(week_opps)} 个）: {', '.join(week_names)}\n"
            f"高风险项目（{len(high_risk_opps)} 个）: {', '.join(risk_names)}\n\n"
            "请给出今日最应该做的事。"
        )

        result = await ai_client.chat(
            messages=[
                {
                    "role": "system",
                    "content": "你是一位销售总监。给出简洁有力的每日建议。",
                },
                {"role": "user", "content": prompt},
            ],
        )

        if isinstance(result, dict):
            return result.get("content", result.get("text", ""))[:500]
        return str(result)[:500]

    except Exception as e:
        logger.error(f"[销售Dashboard] 汇总生成失败: {e}")
        return "暂无 AI 建议"


# 注册到 __init__.py
# 需要在 main.py 中注册: app.include_router(sales_router)