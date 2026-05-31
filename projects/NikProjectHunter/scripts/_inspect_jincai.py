import asyncio
import json
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('http://www.cfcpn.com/jcw/index', wait_until='networkidle')
        await page.wait_for_timeout(3000)

        # 抓取所有公告列表中的标题
        for list_id in ['cgNoticeList', 'zjNoticeList', 'jgNoticeList', 'gzNoticeList']:
            items = await page.query_selector_all(f"#{list_id} .list-group-item")
            print(f"\n=== {list_id} ({len(items)} items) ===")
            for item in items:
                try:
                    link = await item.query_selector("a[onclick*=noticeDetail]")
                    if link:
                        title = (await link.inner_text()).strip()
                        print(f"  [{title[:80]}]")
                except:
                    pass

        await browser.close()

asyncio.run(inspect())