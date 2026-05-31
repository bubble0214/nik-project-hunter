"""Use Playwright's API context with correct URL"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Visit home to establish WAF session
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)
        
        # Use APIRequestContext from context (not page)
        api = context.request
        
        # Use the exact baseURL + path
        resp = await api.post(
            "http://www.ccgp-shandong.gov.cn:8087/api/website/site/getListByCode",
            data=json.dumps({
                "colCode": "0301",
                "area": "370000",
                "currentPage": 1,
                "pageSize": 50,
                "homePage": 0,
                "mergeType": 0,
                "cityType": 1,
            }),
            headers={"Content-Type": "application/json;charset=utf-8"},
        )
        
        print("Status:", resp.status)
        data = await resp.json()
        print("Success:", data.get("success"))
        items = data.get("data", {}).get("data", [])
        print("Items:", len(items))
        
        for item in items[:5]:
            print(f"\n  Title: {item.get('title','')[:60]}")
            print(f"  Date: {item.get('createDate','')}")
            print(f"  ID: {item.get('id','')}")
            print(f"  BulletinType: {item.get('bulletinType','')}")
            print(f"  Area: {item.get('areaName','')}")
        
        # Get detail
        if items:
            item_id = items[0].get("id", "")
            print(f"\n--- Getting detail for {item_id} ---")
            resp2 = await api.get(
                f"http://www.ccgp-shandong.gov.cn:8087/api/website/site/getDetail",
                params={"id": item_id},
            )
            detail = await resp2.json()
            print("Detail success:", detail.get("success"))
            detail_data = detail.get("data", {})
            if detail_data:
                for k, v in detail_data.items():
                    if v:
                        val = str(v)[:200]
                        print(f"  {k}: {val}")
        
        await browser.close()

asyncio.run(main())