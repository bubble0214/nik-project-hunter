"""Try 意向公开 - maybe no captcha needed"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        api_data = []
        async def on_request(req):
            if "getListByCode" in req.url:
                api_data.append({"url": req.url, "post_data": req.post_data})
        async def on_response(resp):
            if "getListByCode" in resp.url:
                try:
                    api_data.append({"url": resp.url, "body": await resp.json()})
                except:
                    pass
        
        page.on("request", on_request)
        page.on("response", on_response)
        
        await page.goto('http://www.ccgp-shandong.gov.cn/xxgk', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Click 意向公开 tab
        for li in await page.query_selector_all("li"):
            text = await li.inner_text()
            if text.strip() == "意向公开":
                print("Clicking 意向公开")
                await li.click()
                await page.wait_for_timeout(3000)
                break
        
        # Check for captcha on intent page
        has_captcha = await page.evaluate("!!document.querySelector('.n-captcha')")
        print(f"Intent page has captcha: {has_captcha}")
        
        # Click 查询 on intent page
        for btn in await page.query_selector_all("button"):
            text = await btn.inner_text()
            if text.strip() == "查询":
                await btn.click()
                await page.wait_for_timeout(5000)
                break
        
        print(f"\nAPI data: {len(api_data)}")
        for d in api_data:
            if "post_data" in d:
                print(f"  REQ: {d['post_data'][:200]}")
            else:
                body = d.get("body", {})
                items = body.get("data", {}).get("data", [])
                print(f"  RESP: success={body.get('success')} items={len(items)}")
                if items:
                    for item in items[:3]:
                        print(f"    {item.get('title','')[:50]} | {item.get('createDate','')}")
                elif body.get('success') == False:
                    print(f"    Error: {json.dumps(body, ensure_ascii=False)[:200]}")
        
        await browser.close()

asyncio.run(main())