"""Extract Shandong ZFCG announcements from home page"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Go to home page and wait for JS to render
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        # Get all visible text to understand layout
        body_text = await page.eval_on_selector("body", "el => el.innerText")
        print("=== BODY TEXT (first 2000 chars) ===")
        print(body_text[:2000])
        
        # Find announcement items - look for links with dates
        links = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({href: e.href, text: e.innerText.trim().substring(0, 80)}))"
        )
        
        # Filter for items with dates (采购公告 items)
        import re
        items = []
        for l in links:
            if l['href'] != 'javascript:void(0)' and len(l['text']) > 10:
                # Check if text contains a date pattern
                if re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', l['text']):
                    items.append(l)
        
        print(f"\n=== Items with dates ({len(items)}) ===")
        for l in items[:30]:
            print(f"  {l['text'][:70]:70s} -> {l['href'][:100]}")
        
        # Also try to find the API endpoint for announcements
        # Check for any script tags containing API URLs
        scripts = await page.eval_on_selector_all("script", "els => els.map(e => e.innerText.substring(0, 500))")
        for s in scripts:
            if 'api' in s.lower() and ('cggg' in s.lower() or 'notice' in s.lower() or 'bulletin' in s.lower()):
                print(f"\nScript with API: {s[:300]}")
        
        await browser.close()

asyncio.run(main())