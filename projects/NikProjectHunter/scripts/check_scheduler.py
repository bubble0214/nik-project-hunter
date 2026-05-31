"""检查 Scheduler 状态"""
import asyncio, httpx, json

async def main():
    async with httpx.AsyncClient() as client:
        r = await client.get("http://localhost:8000/health/detail", timeout=10)
        data = r.json()
        sched = data["scheduler"]
        print("Scheduler:", json.dumps(sched, ensure_ascii=False, indent=2))
        if sched["running"] and sched["jobs"]:
            next_utc = sched["jobs"][0]["next_run"]
            print(f"\n\u2705 Scheduler 正常运行中")
            print(f"   下次触发: {next_utc} UTC")
        else:
            print("\n\u274c Scheduler 有问题")

asyncio.run(main())