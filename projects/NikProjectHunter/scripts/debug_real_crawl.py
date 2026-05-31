import asyncio, json, sys
sys.path.insert(0, '/app')
from app.spiders.jincaiwang import JinCaiWangSpider
from app.pipeline.quality_pipeline import QualityPipeline

async def test():
    spider = JinCaiWangSpider()
    pipeline = QualityPipeline()
    
    print("Starting crawl...")
    raw_projects = await spider.crawl()
    print(f"Crawled {len(raw_projects)} projects")
    
    if raw_projects:
        for i, p in enumerate(raw_projects[:3]):
            print(f'\n--- Project {i} ---')
            print(f'  title: [{p.get("title", "")[:60]}]')
            print(f'  content len: {len(p.get("content", "") or "")}')
            print(f'  source_url: {p.get("source_url", "")[:50]}')
            print(f'  source_platform: {p.get("source_platform", "")}')
            
            cleaned = pipeline._clean(p)
            print(f'  cleaned: {"YES" if cleaned else "NO"}')
            if cleaned:
                kw = pipeline._precision_keyword_filter(cleaned)
                print(f'  keyword passed: {kw["passed"]}, matched: {kw["matched_keywords"][:3]}')

asyncio.run(test())