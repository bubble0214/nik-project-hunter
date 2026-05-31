"""Capture API request data and response"""
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
                post_data = req.post_data
                api_data.append({"type": "req", "url": req.url, "post_data": post_data})
        
        async def on_response(resp):
            if "getListByCode" in resp.url:
                try:
                    body = await resp.json()
                    api_data.append({"type": "resp", "url": resp.url, "body": body})
                except:
                    pass
        
        page.on("request", on_request)
        page.on("response", on_response)
        
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
        
        print(f"API events: {len(api_data)}")
        for d in api_data:
            if d["type"] == "req":
                print(f"\n[REQ] POST to {d['url'][:70]}")
                if d["post_data"]:
                    try:
                        j = json.loads(d["post_data"])
                        print(f"  Params: {json.dumps(j, ensure_ascii=False)[:200]}")
                    except:
                        print(f"  Body: {d['post_data'][:200]}")
            else:
                body = d["body"]
                print(f"\n[RESP] Status: {d['body'].get('success')}")
                items = body.get("data", {}).get("data", [])
                print(f"  Items: {len(items)}")
                if items:
                    for item in items[:3]:
                        print(f"  {item.get('title','')[:50]} | {item.get('createDate','')} | {item.get('id','')}")
                else:
                    print(f"  Full: {json.dumps(body, ensure_ascii=False)[:300]}")
        
        await browser.close()

asyncio.run(main())