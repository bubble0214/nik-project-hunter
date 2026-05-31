import asyncio
from app.database import async_session_factory
from app.models import Project
from sqlalchemy import select, func

async def main():
    async with async_session_factory() as db:
        result = await db.execute(select(func.count(Project.id)))
        total = result.scalar()
        print(f'项目总数: {total}')

        # 查看最新项目
        projects = await db.execute(
            select(Project).order_by(Project.id.desc()).limit(5)
        )
        for p in projects.scalars().all():
            print(f"  - {p.title[:50]}... | {p.source} | score={p.score}")

asyncio.run(main())