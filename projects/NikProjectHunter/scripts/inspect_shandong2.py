"""Deep inspect Shandong ZFCG - JS loaded content"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Intercept network requests to find API endpoints
        api_calls = []
        page.on("response", lambda resp: api_calls.append({
            "url": resp.url,
            "status": resp.status,
            "type": resp.request.resource_type,
        }))
        
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(5000)
        
        print(f"Page title: {await page.title()}")
        print(f"Content length: {len(await page.content())}")
        
        # Look for API/XHR calls
        xhr_calls = [c for c in api_calls if c['type'] in ['xhr', 'fetch']]
        print(f"\nXHR/Fetch calls ({len(xhr_calls)}):")
        for c in xhr_calls[:20]:
            print(f"  [{c['status']}] {c['url'][:120]}")
        
        # Check for any visible text
        body_text = await page.eval_on_selector("body", "el => el.innerText.substring(0, 2000)")
        print(f"\nBody text:\n{body_text[:1000]}")
        
        await browser.close()

asyncio.run(main())