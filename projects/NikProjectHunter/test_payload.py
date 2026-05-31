import asyncio
from app.database import async_session_factory
from app.models import Project
from app.services.notifier import NotifierService
from sqlalchemy import select
from app.config import settings

async def test_payload():
    notifier = NotifierService()
    
    async with async_session_factory() as db:
        result = await db.execute(
            select(Project).where(Project.score.isnot(None)).order_by(Project.score.desc()).limit(1)
        )
        project = result.scalar_one_or_none()
        
        if project:
            title = "测试消息"
            summary = "单条项目测试"
            await notifier.send_report(title, summary, [project])
            
asyncio.run(test_payload())