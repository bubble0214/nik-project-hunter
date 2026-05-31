"""Check actual request URLs being sent from the page"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        all_reqs = []
        page.on("request", lambda req: all_reqs.append({
            "url": req.url, "method": req.method,
        }))
        
        await page.goto('http://www.ccgp-shandong.gov.cn/xxgk', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(5000)
        
        print(f"Total requests: {len(all_reqs)}")
        for r in all_reqs:
            print(f"  {r['method']:6s} {r['url'][:100]}")
        
        await browser.close()

asyncio.run(main())