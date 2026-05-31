"""Capture exact request details from Shandong site"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        requests_detail = []
        page.on("request", lambda r: requests_detail.append({
            "url": r.url,
            "method": r.method,
            "headers": dict(r.headers),
            "post_data": r.post_data,
        }) if "site/getListByCode" in r.url and r.method == "POST" else None)
        
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        for req in requests_detail:
            print(f"\nURL: {req['url']}")
            print(f"Headers: {json.dumps({k:v for k,v in req['headers'].items() if k in ['Content-Type', 'Accept']}, indent=2)}")
            if req['post_data']:
                print(f"POST body: {req['post_data']}")
        
        await browser.close()

import json
asyncio.run(main())