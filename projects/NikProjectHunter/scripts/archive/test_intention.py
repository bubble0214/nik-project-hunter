"""Test intention spiders"""
import asyncio
import sys
sys.path.insert(0, '/app')
from app.spiders.intention_spiders import INTENTION_SPIDERS

async def test():
    for spider in INTENTION_SPIDERS[:3]:
        print(f'\n=== Testing {spider.name} ===')
        try:
            results = await spider.crawl_intents()
            print(f'  Got {len(results)} intents')
            for r in results[:3]:
                title = r.get("title", "")[:60]
                url = r.get("source_url", "")[:60]
                print(f'  - {title}')
                print(f'    url: {url}')
        except Exception as e:
            print(f'  Error: {e}')

asyncio.run(test())