"""Get full API error details"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        api_details = []
        
        async def on_response(resp):
            if "getListByCode" in resp.url:
                try:
                    body = await resp.json()
                    api_details.append({"url": resp.url, "status": resp.status, "body": body})
                except Exception as e:
                    api_details.append({"url": resp.url, "status": resp.status, "error": str(e), "text": await resp.text()})
        
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
        
        print(f"API responses: {len(api_details)}")
        for d in api_details:
            print(f"\nURL: {d['url'][:80]}")
            print(f"Status: {d.get('status')}")
            if "error" in d:
                print(f"Error: {d['error']}")
                print(f"Text: {d['text'][:200]}")
            else:
                body = d["body"]
                print(f"Full response: {json.dumps(body, ensure_ascii=False)[:500]}")
        
        # Also check the page for captcha
        captcha_visible = await page.evaluate("""
            () => {
                const captcha = document.querySelector('[class*="captcha"], img[src*="captcha"], [class*="verify"]');
                return captcha ? captcha.outerHTML : 'No captcha element found';
            }
        """)
        print(f"\nCaptcha check: {captcha_visible}")
        
        await browser.close()

asyncio.run(main())