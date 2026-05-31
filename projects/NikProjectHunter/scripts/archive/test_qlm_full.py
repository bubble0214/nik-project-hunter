"""
全链路测试：千里马爬虫 + Pipeline

直接调用爬虫，验证全流程是否正常。
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEBUG_DIR = Path("/app/debug/qlm_full_test")
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

from app.spiders.beijing_ggzy import QianLiMaSpider
from app.pipeline.quality_pipeline import QualityPipeline
from app.core.logging_config import setup_logging


async def main():
    setup_logging()

    print("=" * 60)
    print("千里马爬虫全链路测试")
    print("=" * 60)

    # 创建爬虫实例
    spider = QianLiMaSpider()

    # 运行爬虫
    print("\n[STEP 1] 启动爬虫...")
    projects = await spider.crawl()

    print(f"\n[STEP 2] 爬虫完成，获取 {len(projects)} 个项目")
    for i, p in enumerate(projects):
        title = p.get("title", "N/A")[:60]
        url = p.get("source_url", "")[:60]
        platform = p.get("source_platform", "")
        region = p.get("region", "")
        buyer = p.get("buyer", "")
        pub_date = p.get("publish_date", "")
        content_len = len(p.get("content", "") or "")
        print(f"  [{i}] {title}")
        print(f"      URL: {url}")
        print(f"      Platform: {platform} | Region: {region} | Buyer: {buyer}")
        print(f"      Date: {pub_date} | Content: {content_len} chars")

    # Pipeline 过滤
    if projects:
        print(f"\n[STEP 3] Pipeline 过滤...")
        pipeline = QualityPipeline()
        filtered = await pipeline.process(projects)
        print(f"  Pipeline 过滤后: {len(filtered)} 个项目")
        for i, p in enumerate(filtered):
            score = p.get("quality_score", 0) or p.get("ai_score", 0)
            title = p.get("title", "N/A")[:60]
            print(f"  [{i}] {title} | Score: {score}")
    else:
        print(f"\n[STEP 3] 无项目需要过滤")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())