"""Capture full API response using route interception"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        responses = []
        
        # Use route to intercept API calls
        await page.route("**/getListByCode", lambda route: asyncio.ensure_future(handle_api(route, responses)))
        
        async def handle_api(route, resp_list):
            response = await route.fetch()
            body = await response.json()
            resp_list.append(body)
            await route.fulfill(response=response)
        
        await page.goto('http://www.ccgp-shandong.gov.cn/xxgk', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Click 采购公告
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
        
        print(f"API responses: {len(responses)}")
        for idx, body in enumerate(responses):
            print(f"\n--- Response {idx+1} ---")
            print(f"Success: {body.get('success')}")
            items = body.get("data", {}).get("data", [])
            print(f"Items: {len(items)}")
            for item in items[:5]:
                print(f"  Title: {item.get('title','')[:50]}")
                print(f"  Date: {item.get('createDate','')}")
                print(f"  ID: {item.get('id','')}")
                print(f"  Area: {item.get('areaName','')}")
                print(f"  BulletinType: {item.get('bulletinType','')}")
                print()
        
        await browser.close()

asyncio.run(main())