"""Capture all POST requests for Shandong ZFCG"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        posts = []
        def on_request(request):
            if request.method == "POST":
                posts.append({
                    "url": request.url,
                    "post_data": request.post_data,
                })
        
        page.on("request", on_request)
        
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        print(f"Total POST requests: {len(posts)}")
        for p_req in posts:
            print(f"\nURL: {p_req['url']}")
            print(f"Body: {p_req['post_data']}")
        
        await browser.close()

asyncio.run(main())