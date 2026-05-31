"""Debug: Test manager pipeline directly with actual crawl data"""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.spiders.jincaiwang import JinCaiWangSpider
from app.pipeline.quality_pipeline import QualityPipeline
from app.database import async_session_factory

async def test():
    spider = JinCaiWangSpider()
    pipeline = QualityPipeline()
    
    print("Starting crawl...")
    raw_projects = await spider.crawl()
    print(f"Crawled {len(raw_projects)} projects")
    
    if raw_projects:
        p = raw_projects[0]
        print(f"Sample project keys: {list(p.keys())}")
        print(f"Sample title: {p.get('title', '')[:80]}")
        print(f"Sample content len: {len(p.get('content', '') or '')}")
        print(f"Sample source_url: {p.get('source_url', '')[:60]}")
        print(f"Sample source_platform: {p.get('source_platform', '')}")
        
        cleaned = pipeline._clean(p)
        print(f"Cleaned: {'YES' if cleaned else 'NO'}")
        if cleaned:
            kw = pipeline._precision_keyword_filter(cleaned)
            print(f"KW match: passed={kw['passed']}, matched={kw['matched_keywords']}")
    
    async with async_session_factory() as session:
        result = await pipeline.process(raw_projects, '金采网', session, run_llm_filter=False)
        print(f"Pipeline result: {json.dumps(result, ensure_ascii=False)}")

asyncio.run(test())