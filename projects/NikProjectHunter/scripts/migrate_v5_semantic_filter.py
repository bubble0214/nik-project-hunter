"""
Nik Project Hunter — 数据库迁移脚本 V5
新增语义过滤字段

新增字段：
- semantic_category: 语义分类
- semantic_score: 语义相关性评分
- matched_signals: 匹配到的语义信号列表
- rejection_reason: 拒绝原因
"""

import asyncio
from loguru import logger
from sqlalchemy import text
from app.database import engine


MIGRATION_SQL = """
ALTER TABLE projects
ADD COLUMN IF NOT EXISTS semantic_category VARCHAR(20) NULL,
ADD COLUMN IF NOT EXISTS semantic_score INTEGER NULL,
ADD COLUMN IF NOT EXISTS matched_signals JSONB NULL,
ADD COLUMN IF NOT EXISTS rejection_reason VARCHAR(200) NULL;

CREATE INDEX IF NOT EXISTS idx_projects_semantic_category ON projects (semantic_category);
CREATE INDEX IF NOT EXISTS idx_projects_semantic_score ON projects (semantic_score);
"""


async def migrate():
    logger.info("=" * 50)
    logger.info("🚀 开始数据库迁移 V5: 语义过滤字段")
    logger.info("=" * 50)

    async with engine.begin() as conn:
        for statement in MIGRATION_SQL.strip().split(";"):
            stmt = statement.strip()
            if not stmt:
                continue
            try:
                await conn.execute(text(stmt))
                logger.info(f"✅ 执行成功: {stmt[:60]}...")
            except Exception as e:
                logger.warning(f"⚠️ 执行失败（可能已存在）: {stmt[:60]}: {e}")

    logger.info("=" * 50)
    logger.info("✅ 数据库迁移 V5 完成")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(migrate())