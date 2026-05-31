"""Debug: Test quality pipeline on jincaiwang data"""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.pipeline.quality_pipeline import QualityPipeline

pipeline = QualityPipeline()

# Simulate jincaiwang detail page result (content empty because selector didn't match)
project = {
    'title': '关于广发银行佛山分行2026年二季度佛驾无忧项目引流方案采购项目单一来源采购的公示',
    'source_url': 'http://www.cfcpn.com/jcw/notice/eb89af675d0045279964f01aaa085cf7',
    'source_platform': '金采网',
    'publish_date': None,
    'region': '广东省',
    'buyer': '广发银行股份有限公司佛山分行',
    'budget': None,
    'content': '',
    'raw_html': '',
}

cleaned = pipeline._clean(project)
print('CLEANED:', 'YES' if cleaned else 'NO')
if not cleaned:
    sys.exit(1)

noise = pipeline._noise_filter(cleaned)
print('NOISE_FILTER:', noise)

kw = pipeline._precision_keyword_filter(cleaned)
print('KEYWORD: passed=' + str(kw['passed']), 'matched=' + str(kw['matched_keywords']))

score = pipeline._calculate_quality_score(cleaned, kw)
print('SCORE:', score)
