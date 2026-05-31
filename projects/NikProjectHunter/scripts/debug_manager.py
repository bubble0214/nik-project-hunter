"""Debug: Test manager crawl_all output"""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.spiders.manager import spider_manager
from app.database import async_session_factory

async def test():
    # Override the spiders list to only test jincaiwang
    from app.spiders.jincaiwang import JinCaiWangSpider
    spider_manager.spiders = [JinCaiWangSpider()]
    
    async with async_session_factory() as session:
        status = await spider_manager.crawl_all(session)
        print('FINAL STATUS:')
        print(json.dumps(status.to_dict(), ensure_ascii=False, indent=2))

asyncio.run(test())