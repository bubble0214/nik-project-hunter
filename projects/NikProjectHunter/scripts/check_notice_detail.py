import asyncio, json, sys
sys.path.insert(0, '/app')
from playwright.async_api import async_playwright
from app.spiders.base.spider import SpiderBase

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
        
        # Go to homepage
        await page.goto('http://www.cfcpn.com/jcw/index', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_load_state('networkidle', timeout=20000)
        await page.wait_for_timeout(3000)
        
        # Check AJAX data interface by monitoring network
        # First get detail.js content via evaluate
        detail_js = await page.evaluate('''() => {
            // Try to get the detail.js content
            var scripts = document.querySelectorAll('script[src*="detail.js"]');
            if (scripts.length > 0) {
                return scripts[0].src;
            }
            return 'not found';
        }''')
        print('detail.js src:', detail_js)
        
        # Try to call the noticeDetail function
        # First check if it exists
        has_func = await page.evaluate('typeof noticeDetail')
        print('noticeDetail type:', has_func)
        
        if has_func == 'function':
            # Check the function source code
            func_src = await page.evaluate('noticeDetail.toString()')
            print('noticeDetail source:', func_src[:2000])
        
        # Also check for any global AJAX endpoints
        ajax_info = await page.evaluate('''() => {
            let info = {};
            // Check jQuery AJAX setup
            if (typeof $ !== 'undefined') {
                info.jquery = $.fn.jquery;
            }
            // Check for base URL or API paths
            if (typeof ctx !== 'undefined') info.ctx = ctx;
            if (typeof basePath !== 'undefined') info.basePath = basePath;
            return info;
        }''')
        print('Global info:', json.dumps(ajax_info, ensure_ascii=False))
        
        await browser.close()

asyncio.run(main())