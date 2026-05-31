import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            url = "http://search.ccgp.gov.cn/bxsearch?searchtype=1&page_index=1&keyword=%E6%95%B0%E6%8D%AE%E5%88%86%E7%B1%BB%E5%88%86%E7%BA%A7&dbselect=bxall&time_type=6"
            print(f"URL: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
            title = await page.title()
            text = await page.evaluate("() => document.body.innerText")
            print(f"TITLE: {title}")
            print(f"FIRST 500: {text[:500]}")
            links = await page.eval_on_selector_all("a[target='_blank']", "els => els.map(e => e.textContent.trim()).filter(Boolean)")
            print(f"LINKS count: {len(links)}")
            for l in links[:10]:
                print(f"  - {l}")
        except Exception as e:
            print(f"ERROR: {e}")
        finally:
            await browser.close()

asyncio.run(test())
