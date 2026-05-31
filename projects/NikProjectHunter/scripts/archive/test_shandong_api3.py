"""Try API via Playwright's internal context"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # First visit home page to get WAF session
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)
        
        # Now use page.evaluate to call fetch API from within browser context
        result = await page.evaluate("""
            async () => {
                const resp = await fetch('http://www.ccgp-shandong.gov.cn:8087/api/website/site/getListByCode', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        colCode: '0301',
                        area: '370000',
                        currentPage: 1,
                        pageSize: 50,
                        homePage: 0,
                        mergeType: 0,
                        cityType: 1
                    })
                });
                const data = await resp.json();
                return data;
            }
        """)
        
        print("Success:", result.get("success"))
        items = result.get("data", {}).get("data", [])
        print("Items:", len(items))
        for item in items[:5]:
            print(f"\n  Title: {item.get('title','')[:60]}")
            print(f"  Date: {item.get('createDate','')}")
            print(f"  ID: {item.get('id','')}")
            print(f"  Area: {item.get('areaName','')}")
        
        # Also get detail page content using the id
        if items:
            item_id = items[0].get("id", "")
            print(f"\n\nTrying to get detail for id={item_id}...")
            
            detail = await page.evaluate("""
                async (id) => {
                    const resp = await fetch('http://www.ccgp-shandong.gov.cn:8087/api/website/site/getBulletin', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({id: id})
                    });
                    const data = await resp.json();
                    return data;
                }
            """, item_id)
            
            print("Detail success:", detail.get("success"))
            detail_data = detail.get("data", {})
            for k, v in detail_data.items():
                if v:
                    val = str(v)[:200]
                    print(f"  {k}: {val}")
        
        await browser.close()

asyncio.run(main())