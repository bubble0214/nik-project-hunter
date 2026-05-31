"""Capture API response from Playwright page"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Capture API responses
        api_responses = []
        page.on("response", lambda resp: api_responses.append({
            "url": resp.url,
            "status": resp.status,
        }) if "getListByCode" in resp.url else None)
        
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(8000)
        
        # Now trigger the announcement load by navigating to /xxgk page
        await page.goto('http://www.ccgp-shandong.gov.cn/xxgk', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        # Also try clicking 采购公告
        for sel in ["span", "a", "li"]:
            els = await page.query_selector_all(sel)
            for el in els:
                text = await el.inner_text()
                if text.strip() == "采购公告":
                    await el.click()
                    await page.wait_for_timeout(3000)
                    break
            else:
                continue
            break
        
        await page.wait_for_timeout(3000)
        
        print(f"API responses captured: {len(api_responses)}")
        for r in api_responses:
            print(f"  [{r['status']}] {r['url'][:100]}")
        
        # Now try to get the actual response data from the page
        print("\nTrying to get announcements from page...")
        announcements = await page.evaluate("""
            async () => {
                const items = [];
                // Look for rendered announcement items
                document.querySelectorAll('a, .el-table__row, tr, .item, [class*="list"] li, div[class*="card"]').forEach(el => {
                    const text = el.innerText?.trim();
                    if (text && text.length > 20 && /(采购|招标|磋商|谈判|询价)/.test(text)) {
                        items.push({
                            text: text.substring(0, 100),
                            html: el.innerHTML.substring(0, 100),
                        });
                    }
                });
                return items.slice(0, 30);
            }
        """)
        
        print(f"Found {len(announcements)} announcement items")
        for a in announcements[:10]:
            print(f"  {a['text'][:80]}")
        
        await browser.close()

asyncio.run(main())