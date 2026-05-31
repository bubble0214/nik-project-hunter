"""Extract cookies from Playwright and use with httpx"""
import asyncio, json, httpx
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Visit home to get cookies
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)
        
        # Get all cookies from context
        cookies = await context.cookies()
        cookie_dict = {c['name']: c['value'] for c in cookies}
        print("Cookies:", json.dumps(cookie_dict, indent=2))
        
        # Build cookie string
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        
        # Try httpx with cookies
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "http://www.ccgp-shandong.gov.cn",
            "Referer": "http://www.ccgp-shandong.gov.cn/home",
            "Cookie": cookie_str,
            "X-Requested-With": "XMLHttpRequest",
        }
        
        payload = {
            "colCode": "0301",
            "area": "370000",
            "currentPage": 1,
            "pageSize": 50,
            "homePage": 0,
            "mergeType": 0,
            "cityType": 1,
        }
        
        # Try with httpx keeping session
        async with httpx.AsyncClient(cookies=cookie_dict, headers=headers, timeout=15) as client:
            r = await client.post(
                "http://www.ccgp-shandong.gov.cn:8087/api/website/site/getListByCode",
                json=payload,
            )
            print(f"\nStatus: {r.status_code}")
            print(f"Response headers: {dict(r.headers)}")
            try:
                data = r.json()
                print("Success:", data.get("success"))
                items = data.get("data", {}).get("data", [])
                print("Items:", len(items))
                for item in items[:3]:
                    print(f"  {item.get('title','')[:50]} | {item.get('createDate','')}")
            except:
                print(f"Response text: {r.text[:200]}")
        
        await browser.close()

asyncio.run(main())