"""
Nik Project Hunter — 数据库初始化脚本

用法：
    python scripts/init_db.py

说明：
    MVP 阶段使用此脚本手动初始化数据库。
    生产环境建议使用 Alembic 管理迁移。
"""

import asyncio
from app.database import init_db, close_db


async def main():
    print("🚀 初始化数据库...")
    await init_db()
    print("✅ 数据库初始化完成")
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())