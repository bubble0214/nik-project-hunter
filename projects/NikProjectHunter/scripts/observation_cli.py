"""
Nik Project Hunter — Observation CLI

Intelligence Observation 手动运行工具

Commands:
  report daily    生成每日 Intelligence Report
  report weekly   生成每周 Intelligence Report
  dashboard       生成 Observation Dashboard
  stats           生成各项统计数据
"""

import asyncio
import json
import sys
from datetime import datetime, timezone, timedelta

from app.database import async_session_factory
from app.services.observation import (
    get_daily_crawl_stats,
    get_keyword_effectiveness,
    get_industry_heatmap,
    get_project_type_stats,
    get_high_value_stats,
    get_trend_intelligence,
    generate_daily_intelligence_report,
    generate_weekly_intelligence_report,
    get_observation_dashboard,
)


def _print_json(data, title=None):
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


async def cmd_report(report_type: str):
    """生成 Intelligence Report"""
    async with async_session_factory() as session:
        if report_type == "weekly":
            report = await generate_weekly_intelligence_report(session)
            _print_json(report, "Weekly Intelligence Report")
        else:
            report = await generate_daily_intelligence_report(session)
            _print_json(report, "Daily Intelligence Report")


async def cmd_dashboard():
    """生成全量 Observation Dashboard"""
    async with async_session_factory() as session:
        data = await get_observation_dashboard(session)
        _print_json(data, "Observation Dashboard")


async def cmd_stats():
    """生成各项统计数据"""
    async with async_session_factory() as session:
        crawl = await get_daily_crawl_stats(session)
        _print_json(crawl, "Daily Crawl Stats")

        kw = await get_keyword_effectiveness(session)
        _print_json(kw, "Keyword Effectiveness")

        industry = await get_industry_heatmap(session)
        _print_json(industry, "Industry Heatmap")

        types = await get_project_type_stats(session)
        _print_json(types, "Project Type Stats")

        hv = await get_high_value_stats(session)
        _print_json(hv, "High Value Stats")

        trends = await get_trend_intelligence(session)
        _print_json(trends, "Trend Intelligence")


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1]

    if command == "report":
        if len(sys.argv) < 3:
            print("Usage: python -m scripts.observation_cli report <daily|weekly>")
            return
        await cmd_report(sys.argv[2])
    elif command == "dashboard":
        await cmd_dashboard()
    elif command == "stats":
        await cmd_stats()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    asyncio.run(main())