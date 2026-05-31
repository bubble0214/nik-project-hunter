"""Find JS files loaded by Shandong ZFCG"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Capture all JS files loaded
        js_files = []
        page.on("request", lambda r: js_files.append(r.url) if r.url.endswith('.js') else None)
        
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)
        
        print(f"JS files loaded: {len(js_files)}")
        for js in js_files[:20]:
            print(f"  {js}")
        
        await browser.close()

asyncio.run(main())