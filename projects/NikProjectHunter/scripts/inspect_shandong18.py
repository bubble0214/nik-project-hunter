"""Capture API response body"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Capture response bodies
        api_bodies = []
        async def on_response(resp):
            if "getListByCode" in resp.url:
                try:
                    body = await resp.json()
                    api_bodies.append({"url": resp.url, "status": resp.status, "body": body})
                except:
                    pass
        
        page.on("response", on_response)
        
        await page.goto('http://www.ccgp-shandong.gov.cn/xxgk', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Click 采购公告 tab
        for li in await page.query_selector_all("li"):
            text = await li.inner_text()
            if text.strip() == "采购公告":
                await li.click()
                await page.wait_for_timeout(2000)
                break
        
        # Click 查询
        for btn in await page.query_selector_all("button"):
            text = await btn.inner_text()
            if text.strip() == "查询":
                await btn.click()
                await page.wait_for_timeout(5000)
                break
        
        print(f"API responses: {len(api_bodies)}")
        for b in api_bodies:
            print(f"\nURL: {b['url'][:80]}")
            data = b['body']
            print(f"Success: {data.get('success')}")
            if data.get('data'):
                items = data.get('data', {}).get('data', [])
                print(f"Items: {len(items)}")
                for item in items[:3]:
                    print(f"  {item.get('title','')[:50]} | {item.get('createDate','')} | id={item.get('id','')}")
            else:
                print(f"Response: {json.dumps(data, ensure_ascii=False)[:300]}")
        
        await browser.close()

asyncio.run(main())