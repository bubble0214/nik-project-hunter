"""Quick check intent detail"""
import asyncio
from app.spiders.tianjin_zfcg import TianjinZFCGSpider

async def test():
    spider = TianjinZFCGSpider()
    intents = await spider.crawl_intents()
    for p in intents[:3]:
        print("Title:", repr(p["title"][:50]) if p.get("title") else "EMPTY")
        print("  Date:", p.get("publish_date"))
        print("  Buyer:", p.get("buyer", "")[:30])
        print()

asyncio.run(test())