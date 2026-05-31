"""
测试新版中国政府采购网爬虫
"""
import sys, os, json, asyncio
sys.path.insert(0, '/app')
os.environ.setdefault('APP_ENV', 'development')

from app.spiders.china_zfcg import ChinaZFCGSpider

async def test():
    spider = ChinaZFCGSpider()
    try:
        projects = await spider.crawl()
        print(f"\n总计: {len(projects)} 个项目\n")
        for i, p in enumerate(projects):
            t = p.get("title", "?")
            buyer = p.get("buyer", "")
            budget = p.get("budget", "")
            content_preview = (p.get("content", "") or "")[:100].replace("\n", " ")
            print(f"  [{i+1}] {t[:70]}")
            if buyer:
                print(f"      采购单位: {buyer}")
            if budget:
                print(f"      预算: {budget}")
            if content_preview:
                print(f"      内容摘要: {content_preview[:80]}")
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await spider.close_browser()

asyncio.run(test())