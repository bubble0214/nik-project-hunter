"""
Nik Project Hunter - Intelligence Observation Engine

7-Day Intelligence Observation Sprint

Functions:
- get_daily_crawl_stats: 每日抓取统计
- get_keyword_effectiveness: 关键词效果统计
- get_industry_heatmap: 行业热度统计
- get_project_type_stats: 项目类型统计
- get_high_value_stats: 高价值项目统计
- get_trend_intelligence: 趋势分析
- generate_daily_intelligence_report: 每日报告
- generate_weekly_intelligence_report: 每周报告
- get_observation_dashboard: 全量聚合
"""

import json
from datetime import datetime, timedelta, timezone
from loguru import logger
from sqlalchemy import func, select
from app.models import Project
from app.core.ai_client import ai_client


# =========================================================================
# 精准关键词（与 quality_pipeline 保持一致）
# =========================================================================

PRECISION_KEYWORDS = {
    "data_governance": [
        "数据治理", "主数据", "数据中台", "数据平台", "数据湖",
        "元数据", "数据标准", "数据质量", "数据目录", "数据血缘",
        "数据架构", "数据模型", "MDM", "湖仓一体", "Data Fabric",
        "数据编织", "ETL", "ELT", "数据仓库", "数据集成",
    ],
    "data_asset": [
        "数据资产", "数据确权", "数据目录", "数据运营", "数据要素",
        "数据估值", "数据入表", "数据交易", "数据流通", "数据共享",
        "数据资本化", "数据资源化", "数据资产化",
    ],
    "ai": [
        "AI平台", "大模型", "智能分析", "AI中台", "机器学习",
        "人工智能", "LLM", "RAG", "知识库", "知识图谱",
        "智能客服", "Copilot", "NLP", "深度学习",
        "智能决策", "智能风控", "智能营销",
    ],
    "data_security": [
        "数据安全", "分类分级", "数据脱敏", "数据风控",
        "数据水印", "数据审计", "隐私计算", "联邦学习",
        "差分隐私", "数据加密", "DLP", "零信任",
        "个人信息保护", "数据合规", "数据出境", "PIPL",
    ],
}

ALL_KEYWORDS = []
for kw_list in PRECISION_KEYWORDS.values():
    ALL_KEYWORDS.extend(kw_list)

CATEGORY_MAP = {}
for cat, kws in PRECISION_KEYWORDS.items():
    for kw in kws:
        CATEGORY_MAP[kw.lower()] = cat


# =========================================================================
# 时间工具
# =========================================================================

def _get_tz():
    return timezone(timedelta(hours=8))


def _today_range():
    tz = _get_tz()
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=24)
    return start, end


# =========================================================================
# 1. 每日抓取统计
# =========================================================================

async def get_daily_crawl_stats(session):
    """统计总抓取量、今日新增、来源分布、状态分布"""
    today_start, today_end = _today_range()

    total_today = await session.scalar(
        select(func.count(Project.id)).where(
            Project.created_at >= today_start,
            Project.created_at < today_end
        )
    ) or 0

    total_all = await session.scalar(select(func.count(Project.id))) or 0

    sr = await session.execute(
        select(Project.source, func.count(Project.id).label("cnt"))
        .group_by(Project.source)
        .order_by(func.count(Project.id).desc())
    )
    by_source = {row[0]: row[1] for row in sr}

    sr2 = await session.execute(
        select(Project.status, func.count(Project.id).label("cnt"))
        .group_by(Project.status)
        .order_by(func.count(Project.id).desc())
    )
    by_status = {row[0]: row[1] for row in sr2}

    return {
        "date": datetime.now(_get_tz()).strftime("%Y-%m-%d"),
        "total_all": total_all,
        "total_today": total_today,
        "by_source": by_source,
        "by_status": by_status,
    }


# =========================================================================
# 2. 关键词效果统计
# =========================================================================

async def get_keyword_effectiveness(session):
    """统计每个精准关键词的命中次数、高价值率、平均分"""
    tz = _get_tz()
    now = datetime.now(tz)
    month_start = now - timedelta(days=30)

    result = await session.execute(
        select(Project).where(Project.created_at >= month_start)
    )
    projects = result.scalars().all()

    kw_hits = {}
    cat_hits = {}

    for p in projects:
        text = ((p.title or "") + " " + (p.summary or "")).lower()
        score = p.score or 0
        is_high = score >= 70

        for kw in ALL_KEYWORDS:
            if kw.lower() in text:
                if kw not in kw_hits:
                    kw_hits[kw] = {"count": 0, "high_value": 0, "total_score": 0}
                kw_hits[kw]["count"] += 1
                kw_hits[kw]["total_score"] += score
                if is_high:
                    kw_hits[kw]["high_value"] += 1

                cat = CATEGORY_MAP.get(kw.lower(), "other")
                if cat not in cat_hits:
                    cat_hits[cat] = {"count": 0, "high_value": 0}
                cat_hits[cat]["count"] += 1
                if is_high:
                    cat_hits[cat]["high_value"] += 1

    total_projects = len(projects)

    kw_sorted = sorted(
        [{
            "keyword": k,
            "count": v["count"],
            "high_value_count": v["high_value"],
            "hit_rate": round(v["count"] / total_projects * 100, 1) if total_projects else 0,
            "high_value_rate": round(v["high_value"] / v["count"] * 100, 1) if v["count"] else 0,
            "avg_score": round(v["total_score"] / v["count"], 1) if v["count"] else 0,
        }
         for k, v in kw_hits.items()],
        key=lambda x: x["count"], reverse=True
    )[:30]

    cat_sorted = sorted(
        [{
            "category": k,
            "count": v["count"],
            "high_value_count": v["high_value"],
            "high_value_rate": round(v["high_value"] / v["count"] * 100, 1) if v["count"] else 0,
        }
         for k, v in cat_hits.items()],
        key=lambda x: x["count"], reverse=True
    )

    return {
        "total_projects_analyzed": total_projects,
        "keywords": kw_sorted,
        "categories": cat_sorted,
    }


# =========================================================================
# 3. 行业热度统计
# =========================================================================

async def get_industry_heatmap(session):
    """统计 7d 和 30d 行业分布"""
    tz = _get_tz()
    now = datetime.now(tz)
    ranges = {"7d": now - timedelta(days=7), "30d": now - timedelta(days=30)}
    result = {}

    for period_name, start in ranges.items():
        query = await session.execute(
            select(Project.analysis).where(
                Project.analysis.isnot(None),
                Project.created_at >= start
            )
        )
        counts = {}
        for row in query:
            a = row[0]
            if isinstance(a, dict):
                ind = a.get("industry_type", "其他")
                counts[ind] = counts.get(ind, 0) + 1
        result[period_name] = sorted(
            [{"industry": k, "count": v} for k, v in counts.items()],
            key=lambda x: x["count"], reverse=True
        )

    return result


# =========================================================================
# 4. 项目类型统计
# =========================================================================

async def get_project_type_stats(session):
    """统计四象限项目类型占比"""
    tz = _get_tz()
    now = datetime.now(tz)
    month_start = now - timedelta(days=30)

    query = await session.execute(
        select(Project.analysis).where(
            Project.analysis.isnot(None),
            Project.created_at >= month_start
        )
    )

    counts = {
        "data_governance": 0,
        "data_asset": 0,
        "ai": 0,
        "data_security": 0,
        "other": 0,
    }
    total_with_analysis = 0

    for row in query:
        total_with_analysis += 1
        a = row[0]
        if not isinstance(a, dict):
            continue
        if a.get("is_data_governance"):
            counts["data_governance"] += 1
        if a.get("is_data_asset"):
            counts["data_asset"] += 1
        if a.get("is_ai_project"):
            counts["ai"] += 1
        if a.get("is_data_security"):
            counts["data_security"] += 1
        if not any([
            a.get("is_data_governance"),
            a.get("is_data_asset"),
            a.get("is_ai_project"),
            a.get("is_data_security"),
        ]):
            counts["other"] += 1

    t = sum(counts.values()) or 1
    return {
        "total_with_analysis": total_with_analysis,
        "type_counts": counts,
        "type_percentages": {k: round(v / t * 100, 1) for k, v in counts.items()},
    }


# =========================================================================
# 5. 高价值项目统计
# =========================================================================

async def get_high_value_stats(session):
    """统计 S/A/B/C 等级分布 + 商机等级分布"""
    tz = _get_tz()
    now = datetime.now(tz)

    async def _grade_counts(s, start=None):
        q = select(
            Project.score_grade,
            func.count(Project.id).label("cnt")
        ).where(Project.score_grade.isnot(None))
        if start:
            q = q.where(Project.created_at >= start)
        r = await s.execute(q.group_by(Project.score_grade))
        return {row[0]: row[1] for row in r}

    total = await _grade_counts(session)
    week = await _grade_counts(session, now - timedelta(days=7))
    month = await _grade_counts(session, now - timedelta(days=30))

    opp_result = await session.execute(
        select(Project.opportunity_level, func.count(Project.id).label("cnt"))
        .where(Project.opportunity_level.isnot(None))
        .group_by(Project.opportunity_level)
    )
    by_opp = {row[0]: row[1] for row in opp_result}

    return {
        "total_by_grade": total,
        "week_by_grade": week,
        "month_by_grade": month,
        "by_opportunity_level": by_opp,
        "s_count": total.get("S", 0),
        "a_count": total.get("A", 0),
        "high_value_total": total.get("S", 0) + total.get("A", 0),
    }


# =========================================================================
# 6. 趋势分析 (Trend Intelligence)
# =========================================================================

async def get_trend_intelligence(session):
    """分析行业趋势、项目类型趋势、活跃买家、预算项目"""
    tz = _get_tz()
    now = datetime.now(tz)
    ranges = {
        "last_7d": now - timedelta(days=7),
        "last_30d": now - timedelta(days=30),
    }

    industry_data = {}
    type_data = {}
    buyer_data = {}
    budget_data = []

    for period_name, start in ranges.items():
        q = await session.execute(
            select(Project).where(
                Project.created_at >= start,
                Project.created_at < now
            )
        )
        projects = q.scalars().all()

        industry_data[period_name] = {}
        type_data[period_name] = {
            "data_governance": 0,
            "data_asset": 0,
            "ai": 0,
            "data_security": 0,
        }
        buyer_data[period_name] = {}

        for p in projects:
            a = p.analysis if isinstance(p.analysis, dict) else {}
            ind = a.get("industry_type", "其他")
            industry_data[period_name][ind] = industry_data[period_name].get(ind, 0) + 1

            if a.get("is_data_governance"):
                type_data[period_name]["data_governance"] += 1
            if a.get("is_data_asset"):
                type_data[period_name]["data_asset"] += 1
            if a.get("is_ai_project"):
                type_data[period_name]["ai"] += 1

            if p.buyer:
                buyer_data[period_name][p.buyer] = buyer_data[period_name].get(p.buyer, 0) + 1

            if p.budget and p.budget > 0:
                budget_data.append({
                    "title": p.title,
                    "budget": p.budget,
                    "created_at": str(p.created_at),
                })

    return {
        "industry_trends": {
            "7d": industry_data.get("last_7d", {}),
            "30d": industry_data.get("last_30d", {}),
        },
        "type_trends": {
            "7d": type_data.get("last_7d", {}),
            "30d": type_data.get("last_30d", {}),
        },
        "active_buyers_7d": sorted(
            [{"buyer": k, "count": v} for k, v in buyer_data.get("last_7d", {}).items()],
            key=lambda x: x["count"], reverse=True
        )[:10],
        "active_buyers_30d": sorted(
            [{"buyer": k, "count": v} for k, v in buyer_data.get("last_30d", {}).items()],
            key=lambda x: x["count"], reverse=True
        )[:10],
        "budget_projects": sorted(budget_data, key=lambda x: x["budget"], reverse=True)[:10],
    }


# =========================================================================
# 7. Daily Intelligence Report
# =========================================================================

async def generate_daily_intelligence_report(session):
    """生成每日 Intelligence Report，含 AI 分析"""
    tz = _get_tz()
    now = datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 今日项目
    today_projects = (await session.execute(
        select(Project).where(
            Project.created_at >= today_start,
            Project.created_at < now
        )
    )).scalars().all()

    # 近 7 天高价值项目
    week_start = now - timedelta(days=7)
    high_value = (await session.execute(
        select(Project).where(
            Project.score_grade.in_(["S", "A"]),
            Project.created_at >= week_start
        ).order_by(Project.score.desc().nullslast()).limit(20)
    )).scalars().all()

    # 行业分布
    month_start = now - timedelta(days=30)
    industry_query = await session.execute(
        select(Project.analysis).where(
            Project.analysis.isnot(None),
            Project.created_at >= month_start
        )
    )
    industry_counts = {}
    for row in industry_query:
        a = row[0]
        if isinstance(a, dict):
            ind = a.get("industry_type", "其他")
            industry_counts[ind] = industry_counts.get(ind, 0) + 1

    today_count = len(today_projects)
    high_value_count = len(high_value)
    top_industries = sorted(industry_counts.items(), key=lambda x: -x[1])[:5]

    high_value_details = []
    for p in high_value[:5]:
        high_value_details.append({
            "title": p.title,
            "buyer": p.buyer,
            "score": p.score,
            "grade": p.score_grade,
            "budget": p.budget,
            "opportunity_level": p.opportunity_level,
        })

    # AI 生成报告
    ai_prompt = (
        '你是一个数据要素行业的 Intelligence 分析师。请基于以下数据，'
        '生成今天的 Intelligence Report。\n\n'
        f'今日新增项目数: {today_count}\n'
        f'近 7 天 S/A 级高价值项目数: {high_value_count}\n'
        f'TOP 行业分布: {json.dumps(top_industries, ensure_ascii=False)}\n'
        f'今日高价值项目: {json.dumps(high_value_details, ensure_ascii=False)}\n\n'
        '请以 JSON 格式返回：\n'
        '{"daily_summary":"今日数据要素市场概况（100字以内）",'
        '"hot_industries":["活跃行业1","活跃行业2","活跃行业3"],'
        '"hot_directions":["升温方向1","升温方向2","升温方向3"],'
        '"ai_trends":"AI 方向趋势（50字）",'
        '"data_asset_trends":"数据资产化趋势（50字）",'
        '"strategic_insight":"战略洞察（50字）",'
        '"key_focus_today":"今日重点关注（50字）"}'
    )
    try:
        ai_result = await ai_client.chat(
            messages=[{"role": "user", "content": ai_prompt}],
            response_format={"type": "json_object"},
            temperature=0.3, max_tokens=1024,
        )
        report = json.loads(ai_result)
    except Exception as e:
        logger.warning(f"[Observation] AI Report 失败: {e}")
        report = {
            "daily_summary": "AI 报告生成失败",
            "hot_industries": [],
            "hot_directions": [],
            "ai_trends": "",
            "data_asset_trends": "",
            "strategic_insight": "",
            "key_focus_today": "",
        }

    return {
        "date": datetime.now(tz).strftime("%Y-%m-%d"),
        "stats": {
            "today_new": today_count,
            "high_value_7d": high_value_count,
            "top_industries": [{"industry": k, "count": v} for k, v in top_industries],
        },
        "high_value_projects": high_value_details,
        "ai_report": report,
        "generated_at": datetime.now(tz).isoformat(),
    }


async def generate_weekly_intelligence_report(session):
    """生成每周 Intelligence Summary，含 AI 分析"""
    tz = _get_tz()
    now = datetime.now(tz)
    week_start = now - timedelta(days=7)

    week_projects = (await session.execute(
        select(Project).where(
            Project.created_at >= week_start,
            Project.created_at < now
        )
    )).scalars().all()

    high_value = (await session.execute(
        select(Project).where(
            Project.score_grade.in_(["S", "A"]),
            Project.created_at >= week_start
        ).order_by(Project.score.desc().nullslast()).limit(20)
    )).scalars().all()

    industry_query = await session.execute(
        select(Project.analysis).where(
            Project.analysis.isnot(None),
            Project.created_at >= week_start
        )
    )
    industry_counts = {}
    for row in industry_query:
        a = row[0]
        if isinstance(a, dict):
            ind = a.get("industry_type", "其他")
            industry_counts[ind] = industry_counts.get(ind, 0) + 1

    week_count = len(week_projects)
    high_value_count = len(high_value)
    top_industries = sorted(industry_counts.items(), key=lambda x: -x[1])[:5]

    high_value_details = []
    for p in high_value[:10]:
        high_value_details.append({
            "title": p.title,
            "buyer": p.buyer,
            "score": p.score,
            "grade": p.score_grade,
            "budget": p.budget,
            "opportunity_level": p.opportunity_level,
        })

    ai_prompt = (
        "你是一个数据要素行业的 Intelligence 分析师。请基于以下数据，"
        "生成本周的 Weekly Intelligence Summary。\n\n"
        f"本周新增项目数: {week_count}\n"
        f"本周 S/A 级高价值项目数: {high_value_count}\n"
        f"TOP 行业分布: {json.dumps(top_industries, ensure_ascii=False)}\n"
        f"本周高价值项目: {json.dumps(high_value_details, ensure_ascii=False)}\n\n"
        "请以 JSON 格式返回：\n"
        '{"weekly_summary":"本周数据要素市场概况（100字以内）",'
        '"hot_industries":["活跃行业1","活跃行业2"],'
        '"hot_directions":["升温方向1","升温方向2"],'
        '"ai_trends":"AI 方向趋势（50字）",'
        '"data_asset_trends":"数据资产化趋势（50字）",'
        '"strategic_clients":["战略客户1","战略客户2"],'
        '"strategic_insight":"战略洞察（50字）",'
        '"key_focus_next":"下周重点关注（50字）"}'
    )

    try:
        ai_result = await ai_client.chat(
            messages=[{"role": "user", "content": ai_prompt}],
            response_format={"type": "json_object"},
            temperature=0.3, max_tokens=1024,
        )
        report = json.loads(ai_result)
    except Exception as e:
        logger.warning(f"[Observation] Weekly Report 失败: {e}")
        report = {
            "weekly_summary": "AI 报告生成失败",
            "hot_industries": [],
            "hot_directions": [],
            "ai_trends": "",
            "data_asset_trends": "",
            "strategic_clients": [],
            "strategic_insight": "",
            "key_focus_next": "",
        }

    return {
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_end": now.strftime("%Y-%m-%d"),
        "stats": {
            "week_new": week_count,
            "high_value_count": high_value_count,
            "top_industries": [{"industry": k, "count": v} for k, v in top_industries],
        },
        "high_value_projects": high_value_details,
        "ai_report": report,
        "generated_at": datetime.now(tz).isoformat(),
    }


async def get_observation_dashboard(session):
    """聚合所有观察数据到单个 Dashboard"""
    crawl_stats = await get_daily_crawl_stats(session)
    kw_eff = await get_keyword_effectiveness(session)
    industry = await get_industry_heatmap(session)
    type_stats = await get_project_type_stats(session)
    hv_stats = await get_high_value_stats(session)
    trends = await get_trend_intelligence(session)

    return {
        "crawl_stats": crawl_stats,
        "keyword_effectiveness": kw_eff,
        "industry_heatmap": industry,
        "project_type_stats": type_stats,
        "high_value_stats": hv_stats,
        "trend_intelligence": trends,
        "updated_at": datetime.now(_get_tz()).isoformat(),
    }
