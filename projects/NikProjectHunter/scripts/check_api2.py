import asyncio, json, sys
sys.path.insert(0, '/app')
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=[
            '--no-sandbox', '--disable-setuid-sandbox',
            '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled',
        ])
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
        )
        page = await context.new_page()
        
        # Intercept ALL network responses
        responses = []
        async def on_response(response):
            url = response.url
            # Capture JS files and API calls
            if url.endswith('.js') or ('/jcw/' in url and 'static' not in url):
                try:
                    body = await response.text()
                    responses.append({'url': url, 'body': body[:500]})
                except:
                    responses.append({'url': url, 'body': '<binary/error>'})
        
        page.on('response', on_response)
        
        await page.goto('http://www.cfcpn.com/jcw/index', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_load_state('networkidle', timeout=20000)
        await page.wait_for_timeout(3000)
        
        # Now call noticeDetail to open a detail page in new window
        async with page.context.expect_page() as new_page_info:
            await page.evaluate('noticeDetail("eb89af675d0045279964f01aaa085cf7","1")')
        detail_page = await new_page_info.value
        await detail_page.wait_for_load_state('networkidle', timeout=20000)
        await detail_page.wait_for_timeout(5000)
        
        # Capture detail page's API responses
        detail_responses = []
        async def on_detail_response(response):
            url = response.url
            if '/jcw/' in url and 'static' not in url:
                try:
                    body = await response.text()
                    detail_responses.append({'url': url, 'body': body[:1000]})
                except:
                    detail_responses.append({'url': url, 'body': '<binary>'})
        
        detail_page.on('response', on_detail_response)
        await detail_page.wait_for_timeout(5000)
        
        print('=== Detail page API responses ===')
        for r in detail_responses:
            print(f'\nURL: {r["url"]}')
            print(f'Body: {r["body"][:500]}')
        
        # Also get the inline scripts from detail page
        scripts = await detail_page.evaluate('''() => {
            let result = [];
            document.querySelectorAll('script').forEach(s => {
                if (s.textContent && s.textContent.length > 10) {
                    result.push(s.textContent.substring(0, 1000));
                }
            });
            return result;
        }''')
        print('\n=== Detail page inline scripts ===')
        for s in scripts:
            print(s[:1000])
            print('---')
        
        await browser.close()

asyncio.run(main())