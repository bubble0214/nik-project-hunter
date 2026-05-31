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
        
        await page.goto('http://www.cfcpn.com/jcw/index', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_load_state('networkidle', timeout=20000)
        await page.wait_for_timeout(3000)
        
        # Get goUrlSearch function source
        func_src = await page.evaluate('''() => {
            if (typeof goUrlSearch !== 'undefined') {
                return goUrlSearch.toString();
            }
            // Also check if it's defined differently
            for (let key in window) {
                if (typeof window[key] === 'function' && key.toLowerCase().includes('go')) {
                    try {
                        return key + ': ' + window[key].toString().substring(0, 500);
                    } catch(e) {}
                }
            }
            return 'not found';
        }''')
        print('goUrlSearch:', func_src)
        
        # Also check if we can directly call the AJAX endpoint
        # The detail page at modules/sys/login/detail likely makes an AJAX call to load data
        # Let's intercept network requests to find the pattern
        api_requests = []
        async def intercept(response):
            url = response.url
            if '/jcw/' in url and response.ok:
                api_requests.append(url)
        
        page.on('response', intercept)
        
        # Open a detail page directly
        await page.goto('http://www.cfcpn.com/jcw/sys/index/goUrl?url=modules/sys/login/detail&column=1&s=eb89af675d0045279964f01aaa085cf7', 
                        wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(10000)
        
        print('\nAPI requests captured:')
        for url in api_requests:
            if 'login' not in url.lower():
                print(f'  {url}')
        
        # Get page content status
        has_title = await page.evaluate('() => document.getElementById("title") ? document.getElementById("title").innerText : "empty"')
        print(f'\nTitle content: [{has_title[:100]}]')
        
        await browser.close()

asyncio.run(main())