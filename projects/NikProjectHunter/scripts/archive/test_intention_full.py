"""Test procurement intention crawl + intelligence"""
import asyncio
import sys
sys.path.insert(0, '/app')
from app.spiders.manager import spider_manager
from app.database import async_session_factory
from app.services.intention_intelligence import intention_intelligence_service

async def test():
    print("=" * 60)
    print("📋 测试采购意向爬取 + Intelligence")
    print("=" * 60)

    async with async_session_factory() as session:
        # Step 1: 爬取意向
        print("\n[Step 1] 爬取采购意向...")
        status = await spider_manager.crawl_all_intents(session)
        await session.commit()
        
        print(f"  发现: {status.total_found}")
        print(f"  新增: {status.total_new}")
        for name, result in status.spider_results.items():
            print(f"  {name}: found={result.get('found', 0)}, new={result.get('new', 0)}")
        
        if status.total_new > 0:
            # Step 2: Intelligence 分析
            print(f"\n[Step 2] 分析 {status.total_new} 个采购意向...")
            results = await intention_intelligence_service.analyze_unanalyzed_intentions(session)
            await session.commit()
            print(f"  分析完成: {len(results)} 个")
            
            target_count = sum(1 for r in results if r.get('is_target', False))
            print(f"  目标赛道: {target_count} 个")
            for r in results:
                if r.get('is_target'):
                    print(f"    - stage={r.get('project_stage')} | window={r.get('engagement_window_score')} | future={r.get('future_opportunity_score')} | level={r.get('opportunity_level')}")
        else:
            print("\n[Step 2] 无新增意向需要分析")
        
        # Step 3: 验证 Dashboard
        print("\n[Step 3] 验证 Intention Dashboard...")
        from app.services.intention_intelligence import intention_dashboard_service
        overview = await intention_dashboard_service.get_overview(session)
        print(f"  总意向: {overview['total']}")
        print(f"  目标赛道: {overview['target_count']}")
        print(f"  高价值: {overview['high_value_count']}")
        
        if overview['top_intentions']:
            print(f"\n  高价值意向 TOP:")
            for i in overview['top_intentions'][:5]:
                print(f"    - {i.get('title', '')[:50]} | stage={i.get('project_stage')} | window={i.get('engagement_window_score')} | future={i.get('future_opportunity_score')}")

    print("\n✅ 测试完成")

asyncio.run(test())