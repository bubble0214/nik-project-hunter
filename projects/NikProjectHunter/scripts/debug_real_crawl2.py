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
    
    for i, p in enumerate(raw_projects):
        title = p.get('title', '')[:60]
        content = p.get('content', '') or ''
        source_platform = p.get('source_platform', '')
        source_url = p.get('source_url', '')[:50]
        print(f'\n--- Project {i} ---')
        print(f'  title: [{title}]')
        print(f'  content len: {len(content)}')
        print(f'  source_platform: [{source_platform}]')
        print(f'  source_url: [{source_url}]')
        
        cleaned = pipeline._clean(p)
        print(f'  cleaned: {"YES" if cleaned else "NO"}')
        if cleaned:
            kw = pipeline._precision_keyword_filter(cleaned)
            print(f'  keyword passed: {kw["passed"]}')
            print(f'  matched keywords: {kw["matched_keywords"]}')
            noise = pipeline._noise_filter(cleaned)
            print(f'  noise: {noise}')
            score = pipeline._calculate_quality_score(cleaned, kw)
            print(f'  score: {score}')

asyncio.run(test())