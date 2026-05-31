"""Click 查询 button precisely"""
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
        }) if "8087" in resp.url else None)
        
        page.on("request", lambda req: api_responses.append({
            "url": req.url, "method": req.method, "type": "request",
        }) if "8087" in req.url else None)
        
        await page.goto('http://www.ccgp-shandong.gov.cn/xxgk', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Click 采购公告 tab
        for li in await page.query_selector_all("li"):
            text = await li.inner_text()
            if text.strip() == "采购公告":
                await li.click()
                await page.wait_for_timeout(2000)
                break
        
        # Click the 查询 button - find by exact text
        for btn in await page.query_selector_all("button"):
            text = await btn.inner_text()
            if text.strip() == "查询":
                print("Clicking 查询 button")
                await btn.click()
                await page.wait_for_timeout(5000)
                break
        
        print(f"\nAPI calls captured: {len(api_responses)}")
        for r in api_responses:
            print(f"  {r}")
        
        # Get the table content
        table_text = await page.evaluate("""
            () => {
                const table = document.querySelector('table, .el-table, [class*="table"]');
                if (table) return table.innerText.substring(0, 500);
                return 'No table found';
            }
        """)
        print(f"\nTable content:\n{table_text}")
        
        # Try to find any announcement text
        all_text = await page.evaluate("document.body.innerText")
        lines = [l.strip() for l in all_text.split('\n') if l.strip()]
        print(f"\nVisible lines (filtered):")
        for l in lines:
            if len(l) > 30 and not l.startswith('http') and '备案' not in l and 'ICP' not in l:
                print(f"  {l[:80]}")
        
        await browser.close()

asyncio.run(main())