"""
Nik Project Hunter — Spider Health Intelligence

职责：
1. 跟踪每个 Spider 的运行健康状态
2. 计算成功率、被封率、质量贡献度
3. 输出 Dashboard API 数据
4. 自动检测 WAF 拦截趋势
"""

import json
import os
import logging
import datetime
from typing import Optional
from loguru import logger

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project

# =============================================================================
# 日志配置
# =============================================================================
HEALTH_LOG_FILE = "logs/spider_health.log"
WAF_LOG_FILE = "logs/waf_detection.log"

os.makedirs("logs", exist_ok=True)

health_logger = logging.getLogger("spider_health")
health_logger.setLevel(logging.INFO)
if not health_logger.handlers:
    fh = logging.FileHandler(HEALTH_LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    health_logger.addHandler(fh)

waf_logger = logging.getLogger("waf_detection")
waf_logger.setLevel(logging.INFO)
if not waf_logger.handlers:
    fh = logging.FileHandler(WAF_LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    waf_logger.addHandler(fh)


# =============================================================================
# 内存状态（每轮爬取后更新）
# =============================================================================
_spider_health_state: dict[str, dict] = {}


def update_spider_health(spider_name: str, metrics: dict):
    """
    更新 Spider 健康指标（由 Manager 在爬取完成后调用）

    metrics 字段:
        - success: bool (是否成功)
        - found: int (发现项目数)
        - new: int (新增项目数)
        - noise_filtered: int
        - keyword_filtered: int
        - llm_filtered: int
        - semantic_filtered: int
        - avg_quality_score: float
        - waf_detected: bool (是否检测到 WAF 拦截)
        - error: str (错误信息，可选)
        - duration_seconds: float (爬取耗时)
    """
    now = datetime.datetime.now()
    state = _spider_health_state.setdefault(spider_name, {
        "spider_name": spider_name,
        "total_runs": 0,
        "successful_runs": 0,
        "failed_runs": 0,
        "waf_detected_count": 0,
        "total_found": 0,
        "total_new": 0,
        "total_filtered": 0,
        "total_quality_score": 0.0,
        "runs_with_quality": 0,
        "last_success_time": None,
        "last_error": None,
        "last_run_time": None,
        "consecutive_failures": 0,
        "health_score": 100,
        "total_duration": 0.0,
    })

    state["total_runs"] += 1
    state["last_run_time"] = now.isoformat()

    if metrics.get("success", True):
        state["successful_runs"] += 1
        state["last_success_time"] = now.isoformat()
        state["consecutive_failures"] = 0
    else:
        state["failed_runs"] += 1
        state["consecutive_failures"] += 1
        state["last_error"] = metrics.get("error", "")

    if metrics.get("waf_detected", False):
        state["waf_detected_count"] += 1
        waf_logger.warning(f"[{spider_name}] WAF 拦截检测 | 累计 {state['waf_detected_count']} 次")

    state["total_found"] += metrics.get("found", 0)
    state["total_new"] += metrics.get("new", 0)
    state["total_filtered"] += (
        metrics.get("noise_filtered", 0)
        + metrics.get("keyword_filtered", 0)
        + metrics.get("llm_filtered", 0)
        + metrics.get("semantic_filtered", 0)
    )

    qs = metrics.get("avg_quality_score", 0)
    if qs > 0:
        state["total_quality_score"] += qs
        state["runs_with_quality"] += 1

    state["total_duration"] += metrics.get("duration_seconds", 0)

    # 计算综合健康评分
    state["health_score"] = _calculate_health_score(state)

    health_logger.info(
        f"[{spider_name}] 状态更新 | "
        f"success={metrics.get('success', True)} | "
        f"found={metrics.get('found', 0)} | "
        f"new={metrics.get('new', 0)} | "
        f"waf={metrics.get('waf_detected', False)} | "
        f"health={state['health_score']:.0f}"
    )

    _spider_health_state[spider_name] = state


def _calculate_health_score(state: dict) -> float:
    """
    计算 Spider 综合健康评分 (0-100)

    因子：
    - 成功率 (40%)
    - WAF 影响 (20%)
    - 数据贡献度 (20%)
    - 连续失败惩罚 (20%)
    """
    if state["total_runs"] == 0:
        return 100.0

    # 成功率
    success_rate = state["successful_runs"] / state["total_runs"]
    score = success_rate * 40

    # WAF 影响
    waf_rate = state["waf_detected_count"] / max(state["total_runs"], 1)
    score += (1 - waf_rate) * 20

    # 数据贡献度
    avg_new = state["total_new"] / max(state["total_runs"], 1)
    data_score = min(avg_new / 5.0, 1.0) * 20
    score += data_score

    # 连续失败惩罚
    consecutive = state["consecutive_failures"]
    if consecutive >= 3:
        penalty = min(consecutive * 5, 20)
        score -= penalty

    return max(0, min(100, score))


def get_spider_health() -> list[dict]:
    """获取所有 Spider 健康状态"""
    results = []
    for name, state in _spider_health_state.items():
        success_rate = (state["successful_runs"] / max(state["total_runs"], 1)) * 100
        block_rate = (state["waf_detected_count"] / max(state["total_runs"], 1)) * 100
        avg_daily = state["total_new"] / max(state["total_runs"], 1)

        results.append({
            "spider_name": name,
            "success_rate": round(success_rate, 1),
            "block_rate": round(block_rate, 1),
            "semantic_pass_rate": round(
                (state["total_new"] / max(state["total_found"], 1)) * 100, 1
            ),
            "avg_quality_score": round(
                state["total_quality_score"] / max(state["runs_with_quality"], 1), 1
            ),
            "avg_daily_projects": round(avg_daily, 1),
            "last_success_time": state.get("last_success_time"),
            "waf_detected": state["waf_detected_count"] > 0,
            "consecutive_failures": state["consecutive_failures"],
            "health_score": round(state["health_score"], 1),
            "total_runs": state["total_runs"],
            "total_new": state["total_new"],
        })
    return results


async def get_spider_health_from_db(session: AsyncSession) -> list[dict]:
    """
    从数据库获取 Spider 历史贡献数据
    补充内存状态
    """
    results = get_spider_health()

    # 从数据库补充每个 Spider 的总项目数
    for r in results:
        try:
            result = await session.execute(
                select(func.count(Project.id)).where(
                    Project.source == r["spider_name"]
                )
            )
            r["total_projects_in_db"] = result.scalar() or 0
        except Exception:
            r["total_projects_in_db"] = 0

    return results


# =============================================================================
# WAF 检测工具
# =============================================================================

WAF_SIGNALS = [
    "Access Verification",
    "频繁访问",
    "验证失败",
    "访问过于频繁",
    "验证码",
    "captcha",
    "challenge",
    "waf",
    "blocked",
    "您的请求",
    "禁止访问",
    "Please verify",
    "Security check",
]


def detect_waf(page_title: str, page_text: str = "") -> bool:
    """
    检测页面是否触发了 WAF 拦截

    Args:
        page_title: 页面标题
        page_text: 页面正文（可选）

    Returns:
        True 如果检测到 WAF
    """
    combined = (page_title + " " + page_text).lower()
    for signal in WAF_SIGNALS:
        if signal.lower() in combined:
            return True
    return False


# =============================================================================
# Trend Intelligence
# =============================================================================

_trend_logger = logging.getLogger("trend_intelligence")
_trend_logger.setLevel(logging.INFO)
if not _trend_logger.handlers:
    fh = logging.FileHandler("logs/trend_intelligence.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    _trend_logger.addHandler(fh)


async def analyze_trends(session: AsyncSession) -> dict:
    """
    趋势信号分析

    分析最近 7 天的项目数据，自动发现：
    - AI 智能体项目增长
    - 数据资产项目增长
    - 行业趋势变化
    - 高频客户
    - 高频采购方向
    """
    try:
        # 查询最近 7 天的项目
        seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        result = await session.execute(
            select(Project).where(Project.created_at >= seven_days_ago)
        )
        recent_projects = result.scalars().all()

        if not recent_projects:
            return {"trends": [], "summary": "最近 7 天无新项目数据"}

        # 按类别统计
        categories = {"data_governance": 0, "data_security": 0, "data_asset": 0, "ai": 0, "unknown": 0}
        opportunity_levels = {"strategic": 0, "high_value": 0, "observation": 0, "weak_signal": 0, "none": 0}
        industries = {}
        buyers = {}

        for p in recent_projects:
            cat = getattr(p, "semantic_category", None) or "unknown"
            categories[cat] = categories.get(cat, 0) + 1

            level = getattr(p, "opportunity_level", None) or "none"
            opportunity_levels[level] = opportunity_levels.get(level, 0) + 1

            if p.analysis and isinstance(p.analysis, dict):
                ind = p.analysis.get("industry_type", "")
                if ind:
                    industries[ind] = industries.get(ind, 0) + 1

            if p.buyer:
                buyers[p.buyer] = buyers.get(p.buyer, 0) + 1

        # 生成趋势报告
        trends = []
        if categories.get("ai", 0) > 0:
            trends.append({
                "signal": "AI 智能体项目增长",
                "count": categories["ai"],
                "percentage": round(categories["ai"] / len(recent_projects) * 100, 1),
            })
        if categories.get("data_asset", 0) > 0:
            trends.append({
                "signal": "数据资产项目增长",
                "count": categories["data_asset"],
                "percentage": round(categories["data_asset"] / len(recent_projects) * 100, 1),
            })
        if categories.get("data_security", 0) > 0:
            trends.append({
                "signal": "数据安全项目增长",
                "count": categories["data_security"],
                "percentage": round(categories["data_security"] / len(recent_projects) * 100, 1),
            })

        # 高频客户
        top_buyers = sorted(buyers.items(), key=lambda x: -x[1])[:10]

        # 高频行业
        top_industries = sorted(industries.items(), key=lambda x: -x[1])[:5]

        report = {
            "trends": trends,
            "summary": {
                "total_recent_projects": len(recent_projects),
                "category_distribution": categories,
                "opportunity_distribution": opportunity_levels,
                "top_buyers": [{"name": k, "count": v} for k, v in top_buyers],
                "top_industries": [{"name": k, "count": v} for k, v in top_industries],
            },
        }

        _trend_logger.info(f"趋势分析完成 | 项目数: {len(recent_projects)} | 趋势: {[t['signal'] for t in trends]}")
        return report

    except Exception as e:
        logger.error(f"[TrendIntelligence] 趋势分析异常: {e}")
        return {"trends": [], "summary": f"分析失败: {e}"}
