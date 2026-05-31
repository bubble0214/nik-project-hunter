"""Use existing axios instance in the page"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        # The page has loaded Vue + axios. We can access the window.axios instance
        # or we can use the already-existing Vue app's methods
        
        result = await page.evaluate("""
            async () => {
                // Try to find the axios instance in the page's Vue app
                // First, let's try a simple fetch via the proxy
                try {
                    // The page makes requests to :8087/api - these work because
                    // the browser's CORS policy is satisfied by the Vue app origin
                    const resp = await fetch('http://www.ccgp-shandong.gov.cn:8087/api/website/site/getListByCode', {
                        method: 'POST',
                        credentials: 'include',
                        mode: 'cors',
                        headers: {'Content-Type': 'application/json;charset=utf-8'},
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
                    return await resp.json();
                } catch(e) {
                    return {error: e.message, stack: e.stack};
                }
            }
        """)
        
        print("Success:", result.get("success"))
        if "error" in result:
            print("Error:", result.get("error"))
            print("Stack:", result.get("stack", "")[:500])
        else:
            items = result.get("data", {}).get("data", [])
            print("Items:", len(items))
            for item in items[:5]:
                print(f"\n  Title: {item.get('title','')[:60]}")
                print(f"  Date: {item.get('createDate','')}")
                print(f"  ID: {item.get('id','')}")
        
        await browser.close()

asyncio.run(main())