import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('http://www.cfcpn.com/jcw/index', wait_until='networkidle')
        await page.wait_for_timeout(2000)

        js = await page.evaluate(
            '() => window.noticeDetail ? window.noticeDetail.toString().substring(0,500) : "not found"'
        )
        print(f'noticeDetail JS: {js}')

        frames = page.frames
        print(f'Frames: {len(frames)}')
        for f in frames:
            print(f'  Frame: {f.url[:100]}')

        try:
            result = await page.evaluate(
                'noticeDetail("94f288498e3542a8b5663a80e2812a34","1")'
            )
            print(f'After noticeDetail: {result}')
            await page.wait_for_timeout(5000)
            print(f'New URL: {page.url}')
            print(f'New pages: {len(page.context.pages)}')
            for p2 in page.context.pages:
                print(f'  Page: {p2.url[:120]}')
                text = await p2.evaluate('document.body.innerText')
                print(f'  Text: {text[:200]}')
        except Exception as e:
            print(f'Error: {e}')

        await browser.close()

asyncio.run(test())