"""
快速全链路测试 — 验证爬虫修复 + Webhook 通知
只跑千里马 + 金采网（跳过慢速的中国政府采购网）
"""
import asyncio
import sys
import signal
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
    print("快速全链路测试")
    print("=" * 60)

    # 设置 5 分钟超时
    loop = asyncio.get_event_loop()
    timeout_handle = None

    # 临时禁用中国政府采购网
    spider_manager.spiders = [s for s in spider_manager.spiders if s.name != "china_zfcg"]

    async with async_session_factory() as session:
        # Step 1: 只跑千里马 + 金采网
        print("\n[Step 1/4] 爬取（跳过中国政府采购网）...")
        try:
            status = await asyncio.wait_for(
                spider_manager.crawl_all(session),
                timeout=300
            )
            print(f"  发现: {status.total_found} | 新增: {status.total_new}")
            if status.spider_results:
                for name, sr in status.spider_results.items():
                    print(f"  {name}: found={sr.get('found',0)} new={sr.get('new',0)}")
            await session.commit()
        except asyncio.TimeoutError:
            print("  ⚠️ 爬取超时（5分钟）")

        # Step 2: AI 分析
        print("\n[Step 2/4] AI 分析...")
        analyzed = await analyzer_service.analyze_unanalyzed_projects(session)
        await session.commit()
        print(f"  分析完成: {len(analyzed)} 个项目")

        # Step 3: AI 评分
        print("\n[Step 3/4] AI 评分...")
        scored = await scorer_service.score_analyzed_projects(session)
        await session.commit()
        print(f"  评分完成: {len(scored)} 个项目")

        # Step 4: 推送通知（所有已评分项目）
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

        # 列出所有项目
        print("\n  📋 项目列表：")
        for p in all_p.scalars().all():
            pid = str(p.id)[:8]
            print(f"    [{pid}] {p.title[:55]} | {p.score} {p.score_grade} | {p.source}")

    print("\n测试完成")


if __name__ == "__main__":
    asyncio.run(main())