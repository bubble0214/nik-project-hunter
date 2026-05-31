"""触发完整流水线 + 检查 Scheduler 状态"""
import asyncio, httpx, json

async def main():
    async with httpx.AsyncClient() as client:
        # 触发流水线
        print("触发完整流水线...")
        r = await client.post("http://localhost:8000/api/v1/crawl/full-pipeline", timeout=600)
        data = r.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print()

        # 检查 scheduler
        r2 = await client.get("http://localhost:8000/health/detail", timeout=10)
        sched = r2.json()["scheduler"]
        print("Scheduler:", json.dumps(sched, ensure_ascii=False, indent=2))

asyncio.run(main())