import asyncio
from app.database import async_session_factory
from app.models import Project
from app.services.notifier import NotifierService
from sqlalchemy import select

async def send_report():
    notifier = NotifierService()
    
    async with async_session_factory() as db:
        result = await db.execute(
            select(Project).where(
                Project.score.isnot(None)
            ).order_by(Project.score.desc())
        )
        projects = result.scalars().all()
        
        print(f'已评分项目: {len(projects)} 条')
        
        if projects:
            title = "Nik Project Hunter - 日报"
            summary = f"共推送 {len(projects)} 条商机"
            await notifier.send_report(title, summary, projects)
            print('日报已推送')
        else:
            print('无已评分项目')

asyncio.run(send_report())