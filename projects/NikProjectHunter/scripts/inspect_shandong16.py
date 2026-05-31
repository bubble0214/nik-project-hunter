"""Trigger announcement query on Shandong ZFCG"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        api_responses = []
        page.on("response", lambda resp: api_responses.append({
            "url": resp.url, "status": resp.status,
        }) if "getListByCode" in resp.url or "getList" in resp.url else None)
        
        await page.goto('http://www.ccgp-shandong.gov.cn/xxgk', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Click 采购公告 tab
        for sel in ["span", "li", "a", "div[class*='tab']"]:
            els = await page.query_selector_all(sel)
            for el in els:
                text = await el.inner_text()
                if text.strip() == "采购公告":
                    await el.click()
                    await page.wait_for_timeout(2000)
                    break
            else:
                continue
            break
        
        # Find and click the query/search button
        print("Looking for query button...")
        buttons = await page.query_selector_all("button, [type='submit'], [class*='query'], [class*='search'], [class*='btn']")
        for btn in buttons:
            text = await btn.inner_text()
            print(f"  Button: '{text.strip()[:30]}' class={await btn.get_attribute('class') or ''}")
        
        # Try clicking buttons that might trigger search
        for btn in buttons:
            text = await btn.inner_text()
            if '查询' in text or '搜索' in text or '检索' in text:
                print(f"\nClicking: {text.strip()}")
                await btn.click()
                await page.wait_for_timeout(3000)
                break
        
        await page.wait_for_timeout(3000)
        
        print(f"\nAPI calls captured: {len(api_responses)}")
        for r in api_responses:
            print(f"  [{r['status']}] {r['url'][:100]}")
        
        # Check what rendered
        body = await page.evaluate("document.body.innerText")
        # Find the table area
        table_start = body.find("序号")
        if table_start >= 0:
            print(f"\nTable area:\n{body[table_start:table_start+500]}")
        else:
            print(f"\nFull body (last 500):\n{body[-500:]}")
        
        await browser.close()

asyncio.run(main())