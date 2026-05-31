"""Debug: Test full pipeline.process() with LLM filter"""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.pipeline.quality_pipeline import QualityPipeline
from app.database import async_session_factory

async def test():
    pipeline = QualityPipeline()
    
    projects = [{
        'title': '关于广发银行佛山分行2026年二季度佛驾无忧项目引流方案采购项目单一来源采购的公示',
        'source_url': 'http://www.cfcpn.com/jcw/notice/eb89af675d0045279964f01aaa085cf7',
        'source_platform': '金采网',
        'publish_date': None,
        'region': '广东省',
        'buyer': '广发银行股份有限公司佛山分行',
        'budget': None,
        'content': '',
        'raw_html': '',
    }]
    
    async with async_session_factory() as session:
        result = await pipeline.process(projects, '金采网', session, run_llm_filter=True)
        print('RESULT (with LLM):', json.dumps(result, ensure_ascii=False, indent=2))

asyncio.run(test())