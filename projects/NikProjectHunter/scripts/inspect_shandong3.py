"""Find Shandong ZFCG announcement list URL"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Capture XHR
        xhrs = []
        page.on("response", lambda r: xhrs.append({"url": r.url, "status": r.status}) if r.request.resource_type in ["xhr", "fetch"] else None)
        
        # Go to 采购公告 list
        await page.goto('http://www.ccgp-shandong.gov.cn/xxgk', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        print(f"Page title: {await page.title()}")
        
        # Get all links
        links = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({href: e.href, text: e.innerText.trim().substring(0, 60)}))"
        )
        
        # Find procurement announcement links
        ann = [l for l in links if any(k in l['href'] for k in ['cggg', 'notice', 'bulletin', 'xxgk'])]
        print(f"\nProcurement links ({len(ann)}):")
        for l in ann[:30]:
            print(f"  {l['text'][:50]:50s} -> {l['href'][:100]}")
        
        # Click 采购公告 tab
        tab = await page.query_selector("text=采购公告")
        if tab:
            await tab.click()
            await page.wait_for_timeout(3000)
            
            links2 = await page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => ({href: e.href, text: e.innerText.trim().substring(0, 60)}))"
            )
            items = [l for l in links2 if len(l['text']) > 10 and l['href'] != 'javascript:void(0)']
            print(f"\n采购公告 items ({len(items)}):")
            for l in items[:15]:
                print(f"  {l['text'][:50]:50s} -> {l['href'][:100]}")
        
        # Print XHRs
        print(f"\nAll XHR calls:")
        for x in xhrs:
            if 'api' in x['url']:
                print(f"  [{x['status']}] {x['url'][:120]}")
        
        await browser.close()

asyncio.run(main())