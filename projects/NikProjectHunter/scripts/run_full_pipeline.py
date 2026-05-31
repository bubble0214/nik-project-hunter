"""
全链路手动触发测试 + 企业微信通知
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import async_session_factory
from app.spiders.manager import spider_manager
from app.services.analyzer import analyzer_service
from app.services.scorer import scorer_service
from app.services.notifier import notifier_service
from sqlalchemy import select
from app.models import Project


async def main():
    print("=" * 60)
    print("全链路手动触发测试")
    print("=" * 60)

    async with async_session_factory() as session:
        # Step 1: 爬取
        print("\n[Step 1/4] 爬取...")
        status = await spider_manager.crawl_all(session)
        print(f"  发现: {status.total_found} | 新增: {status.total_new}")
        if status.spider_results:
            for name, sr in status.spider_results.items():
                print(f"  {name}: found={sr.get('found',0)} new={sr.get('new',0)}")
        await session.commit()

        # Step 2: 分析
        print("\n[Step 2/4] AI 分析...")
        analyzed = await analyzer_service.analyze_unanalyzed_projects(session)
        await session.commit()
        print(f"  分析完成: {len(analyzed)} 个项目")

        # Step 3: 评分
        print("\n[Step 3/4] AI 评分...")
        scored = await scorer_service.score_analyzed_projects(session)
        await session.commit()
        print(f"  评分完成: {len(scored)} 个项目")

        # Step 4: 通知
        print("\n[Step 4/4] 推送通知...")
        all_projects = await session.execute(
            select(Project).where(Project.score.isnot(None)).order_by(Project.score.desc())
        )
        all_notify = list(all_projects.scalars().all())
        notified = 0
        for p in all_notify:
            if await notifier_service.notify_high_value_project(p):
                notified += 1
        print(f"  通知: {notified}/{len(all_notify)} 个")

        # 汇总
        all_p = await session.execute(select(Project))
        total = len(all_p.scalars().all())
        print(f"\n  📊 数据库总计: {total} 个项目")

    print("\n全链路测试完成")


if __name__ == "__main__":
    asyncio.run(main())