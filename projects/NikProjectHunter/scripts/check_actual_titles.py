"""
实时爬虫诊断 — 查看爬虫抓取的实际标题
"""
import sys, os, json, asyncio
sys.path.insert(0, '/app')
os.environ.setdefault('APP_ENV', 'development')

from app.spiders.china_zfcg import ChinaZFCGSpider
from app.spiders.jincaiwang import JinCaiWangSpider
from app.spiders.beijing_ggzy import QianLiMaSpider

async def test_china_zfcg():
    print("=" * 60)
    print("中国政府采购网 — 实际抓取标题")
    print("=" * 60)
    spider = ChinaZFCGSpider()
    try:
        projects = await spider.crawl()
        print(f"\n总计: {len(projects)} 个项目\n")
        for i, p in enumerate(projects):
            t = p.get("title", "?")
            kw = p.get("publish_date", "")
            print(f"  [{i+1}] {t[:80]}")
    except Exception as e:
        print(f"错误: {e}")
    finally:
        await spider.close_browser()

async def test_jincaiwang():
    print("\n" + "=" * 60)
    print("金采网 — 实际抓取标题")
    print("=" * 60)
    spider = JinCaiWangSpider()
    try:
        projects = await spider.crawl()
        print(f"\n总计: {len(projects)} 个项目\n")
        for i, p in enumerate(projects):
            t = p.get("title", "?")
            print(f"  [{i+1}] {t[:80]}")
    except Exception as e:
        print(f"错误: {e}")
    finally:
        await spider.close_browser()

async def test_qianlima():
    print("\n" + "=" * 60)
    print("千里马 — 实际抓取标题")
    print("=" * 60)
    spider = QianLiMaSpider()
    try:
        projects = await spider.crawl()
        print(f"\n总计: {len(projects)} 个项目\n")
        for i, p in enumerate(projects):
            t = p.get("title", "?")
            print(f"  [{i+1}] {t[:80]}")
    except Exception as e:
        print(f"错误: {e}")
    finally:
        await spider.close_browser()

async def main():
    await test_china_zfcg()
    # await test_jincaiwang()
    # await test_qianlima()

asyncio.run(main())