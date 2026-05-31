"""
Nik Project Hunter — Data Quality Sprint CLI

DataOps Engineer 工具：
1. cleanup_noise — 清理数据库中已存在的噪声项目
2. quality_report — 生成数据质量报告
3. dedup_check — 检查重复项目
4. run_stats — 运行统计
"""

import asyncio
import json
import sys
from datetime import datetime
from loguru import logger
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, init_db, close_db
from app.models import Project
from app.pipeline.quality_pipeline import (
    cleanup_noise_projects,
    generate_quality_report,
    ALL_PRECISION_KEYWORDS,
    NOISE_KEYWORDS,
)


async def run_cleanup():
    """运行噪声清理"""
    logger.info("=" * 60)
    logger.info("🧹 开始数据库噪声清理")
    logger.info("=" * 60)

    await init_db()
    async with async_session_factory() as session:
        result = await cleanup_noise_projects(session)
        await session.commit()

    logger.info(f"✅ 清理完成: 删除 {result['deleted']} 个, 保留 {result['kept']} 个")
    await close_db()
    return result


async def run_report():
    """生成数据质量报告"""
    logger.info("=" * 60)
    logger.info("📊 生成数据质量报告")
    logger.info("=" * 60)

    await init_db()
    async with async_session_factory() as session:
        report = await generate_quality_report(session)

    print("\n" + "=" * 50)
    print("📊 Data Quality Report")
    print("=" * 50)
    print(f"项目总数: {report['total_projects']}")
    print(f"\n按来源分布:")
    for source, count in sorted(report['by_source'].items(), key=lambda x: -x[1]):
        print(f"  {source}: {count} 个")
    print(f"\n按状态分布:")
    for status, count in sorted(report['by_status'].items(), key=lambda x: -x[1]):
        print(f"  {status}: {count} 个")
    print("=" * 50)

    await close_db()
    return report


async def run_dedup_check():
    """检查重复项目"""
    logger.info("=" * 60)
    logger.info("🔍 检查重复项目")
    logger.info("=" * 60)

    await init_db()
    async with async_session_factory() as session:
        result = await session.execute(
            select(Project.source_url, func.count(Project.id).label("cnt"))
            .group_by(Project.source_url)
            .having(func.count(Project.id) > 1)
        )
        duplicates = result.all()

    if duplicates:
        print(f"\n发现 {len(duplicates)} 个重复 URL:")
        for url, cnt in duplicates:
            print(f"  [{cnt}x] {url[:80]}")
    else:
        print("\n✅ 无重复项目")

    await close_db()
    return len(duplicates)


async def run_stats():
    """运行统计"""
    await init_db()
    async with async_session_factory() as session:
        # 总数
        total = await session.execute(select(func.count(Project.id)))
        total_count = total.scalar()

        # 按来源
        by_source = await session.execute(
            select(Project.source, func.count(Project.id))
            .group_by(Project.source)
            .order_by(func.count(Project.id).desc())
        )

        # 按状态
        by_status = await session.execute(
            select(Project.status, func.count(Project.id))
            .group_by(Project.status)
            .order_by(func.count(Project.id).desc())
        )

        # 按评分等级
        by_grade = await session.execute(
            select(Project.score_grade, func.count(Project.id))
            .group_by(Project.score_grade)
            .order_by(func.count(Project.id).desc())
        )

        # 按商机级别
        by_opp = await session.execute(
            select(Project.opportunity_level, func.count(Project.id))
            .group_by(Project.opportunity_level)
            .order_by(func.count(Project.id).desc())
        )

        # 最新项目
        recent = await session.execute(
            select(Project).order_by(Project.created_at.desc()).limit(5)
        )
        recent_projects = recent.scalars().all()

    print("\n" + "=" * 60)
    print("🏆 Nik Project Hunter — 系统统计")
    print("=" * 60)
    print(f"总项目数: {total_count}")
    print()

    print("按来源分布:")
    for row in by_source:
        print(f"  {row[0]}: {row[1]} 个")
    print()

    print("按状态分布:")
    for row in by_status:
        print(f"  {row[0]}: {row[1]} 个")
    print()

    if by_grade:
        print("按评分等级:")
        for row in by_grade:
            print(f"  {row[0] or 'N/A'}: {row[1]} 个")
        print()

    if by_opp:
        print("按商机级别:")
        for row in by_opp:
            print(f"  {row[0] or 'N/A'}: {row[1]} 个")
        print()

    print("最新 5 个项目:")
    for p in recent_projects:
        print(f"  [{p.source}] {p.title[:60]}... | 评分: {p.score or 'N/A'} | {p.status}")
    print("=" * 60)

    await close_db()


async def main():
    """主入口"""
    if len(sys.argv) < 2:
        print("用法: python scripts/quality_cli.py <command>")
        print("命令:")
        print("  cleanup    清理噪声项目")
        print("  report     生成质量报告")
        print("  dedup      检查重复项目")
        print("  stats      运行统计")
        return

    command = sys.argv[1]

    if command == "cleanup":
        await run_cleanup()
    elif command == "report":
        await run_report()
    elif command == "dedup":
        await run_dedup_check()
    elif command == "stats":
        await run_stats()
    else:
        print(f"未知命令: {command}")
        print("可用命令: cleanup, report, dedup, stats")


if __name__ == "__main__":
    asyncio.run(main())