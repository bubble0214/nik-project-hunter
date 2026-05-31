"""Check table existence"""
import asyncio
from app.database import engine
from app.models import ProcurementIntention

async def check():
    async with engine.begin() as conn:
        from sqlalchemy import text
        result = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'procurement_intentions')"
        ))
        exists = result.scalar()
        print(f"procurement_intentions table exists: {exists}")
        print(f"Model fields: {len(ProcurementIntention.__table__.columns)}")
        for col in ProcurementIntention.__table__.columns:
            print(f"  {col.name}: {col.type}")

asyncio.run(check())
