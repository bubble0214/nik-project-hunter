"""Capture getListByCode response body via page route interception"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        api_bodies = []
        
        # Use route interception to capture and read response body
        async def handle_route(route):
            # Let the request go through
            response = await route.fetch()
            if "getListByCode" in response.url:
                try:
                    body = await response.json()
                    api_bodies.append(body)
                except:
                    pass
            await route.fulfill(response=response)
        
        await page.route("**/getListByCode", handle_route)
        
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
        
        print(f"API responses captured: {len(api_bodies)}")
        for idx, body in enumerate(api_bodies):
            print(f"\n--- Response {idx+1} ---")
            print(f"Success: {body.get('success')}")
            if body.get('data'):
                items = body.get('data', {}).get('data', [])
                print(f"Items: {len(items)}")
                for item in items[:3]:
                    print(f"  {item.get('title','')[:50]} | {item.get('createDate','')} | id={item.get('id','')}")
            else:
                print(f"Body: {json.dumps(body, ensure_ascii=False)[:300]}")
        
        await browser.close()

asyncio.run(main())