"""Analyze Shandong ZFCG page source for API calls"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)
        
        # Get the raw HTML
        html = await page.content()
        
        # Search for API endpoints, colCode definitions, or JS config
        import re
        
        # Find all script tags content
        scripts = await page.eval_on_selector_all("script", "els => els.map(e => e.innerText)")
        
        for idx, script in enumerate(scripts):
            if len(script) > 50:
                # Look for keywords
                if any(k in script for k in ['colCode', '0301', 'getListByCode', 'getBulletin', 'api']):
                    print(f"\n=== Script {idx} (len={len(script)}) ===")
                    # Print relevant lines
                    lines = script.split('\n')
                    for line in lines:
                        if any(k in line for k in ['colCode', 'api', '0301', 'getList', 'bulletin', 'fetch', 'axios']):
                            print(f"  {line.strip()[:200]}")
        
        # Also check the page for config objects
        html_lower = html.lower()
        for keyword in ['colcode', 'getlistbycode', 'getbulletin', 'api/website']:
            idx = html_lower.find(keyword)
            if idx >= 0:
                print(f"\nFound '{keyword}' at position {idx}:")
                print(f"  {html[max(0,idx-50):idx+150]}")
        
        await browser.close()

asyncio.run(main())