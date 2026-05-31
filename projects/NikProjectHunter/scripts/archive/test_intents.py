"""Test intents"""
import asyncio
from app.spiders.tianjin_zfcg import TianjinZFCGSpider
from app.spiders.hebei_zfcg import HebeiZFCGSpider

async def test():
    spider_tj = TianjinZFCGSpider()
    tianjin = await spider_tj.crawl_intents()
    print("天津采购意向:", len(tianjin), "条")
    for p in tianjin[:3]:
        print(" ", p["title"][:50], "|", p.get("publish_date",""))
    
    spider_hb = HebeiZFCGSpider()
    hebei = await spider_hb.crawl_intents()
    print("河北采购意向:", len(hebei), "条")
    for p in hebei[:3]:
        print(" ", p["title"][:50], "|", p.get("region",""))

asyncio.run(test())