import asyncio
from app.database import async_session_factory
from app.models import Project
from sqlalchemy import delete

async def clear_projects():
    async with async_session_factory() as db:
        await db.execute(delete(Project))
        await db.commit()
        print("已清空 projects 表")

asyncio.run(clear_projects())