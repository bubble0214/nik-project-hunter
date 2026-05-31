"""
测试金采网爬虫 + Pipeline 入库
"""
import sys, os, json, asyncio
sys.path.insert(0, '/app')
os.environ['APP_ENV'] = 'development'

from app.database import get_db
from app.spiders.jincaiwang import JinCaiWangSpider
from app.pipeline.pipeline import pipeline

async def main():
    spider = JinCaiWangSpider()
    projects = []
    try:
        projects = await spider.crawl()
    finally:
        await spider.close_browser()
    
    print('爬取到 %d 个项目' % len(projects))
    for p in projects:
        t = p.get('title', '?')
        buyer = p.get('buyer', '')
        budget = p.get('budget', '')
        print('  [%s] buyer=%s budget=%s' % (t[:60], str(buyer)[:20], str(budget)))
    
    # 入库
    async for db in get_db():
        stats = await pipeline.process(projects, '金采网', db)
        await db.commit()
        print('入库统计:', json.dumps(stats, ensure_ascii=False))

asyncio.run(main())