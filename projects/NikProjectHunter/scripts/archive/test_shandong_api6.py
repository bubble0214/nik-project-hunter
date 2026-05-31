"""Use page.evaluate to call API with proper CORS"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Go to home first
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)
        
        # Use page.evaluate with fetch - but the issue is CORS/no-cors
        # Try with no-cors mode
        result = await page.evaluate("""
            async () => {
                try {
                    const resp = await fetch('http://www.ccgp-shandong.gov.cn:8087/api/website/site/getListByCode', {
                        method: 'POST',
                        mode: 'no-cors',
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
                    const text = await resp.text();
                    try {
                        return JSON.parse(text);
                    } catch(e) {
                        return {error: 'parse_failed', text: text.substring(0, 200)};
                    }
                } catch(e) {
                    return {error: e.message};
                }
            }
        """)
        
        print("Result keys:", list(result.keys())[:10])
        print("Success:", result.get("success"))
        if result.get("data"):
            items = result.get("data", {}).get("data", [])
            print("Items:", len(items))
            for item in items[:3]:
                print(f"  {item.get('title','')[:50]} | {item.get('createDate','')} | {item.get('id','')}")
        else:
            print("Full result:", json.dumps(result, ensure_ascii=False, indent=2)[:500])
        
        await browser.close()

asyncio.run(main())