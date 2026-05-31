"""Capture Shandong ZFCG API requests"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Capture all requests with POST data
        requests_data = []
        page.on("request", lambda r: requests_data.append({
            "url": r.url,
            "method": r.method,
            "headers": dict(r.headers),
            "post_data": r.post_data,
        }) if "api" in r.url else None)
        
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        print(f"API calls captured: {len(requests_data)}")
        for req in requests_data[:20]:
            print(f"\n  [{req['method']}] {req['url'][:120]}")
            if req['post_data']:
                print(f"    POST: {req['post_data'][:300]}")
        
        await browser.close()

asyncio.run(main())