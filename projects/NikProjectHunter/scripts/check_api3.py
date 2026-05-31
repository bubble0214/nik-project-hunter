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
        
        # Open detail page directly in same window
        await page.goto('http://www.cfcpn.com/jcw/sys/index/goUrl?url=modules/sys/login/detail&column=1&searchVal=eb89af675d0045279964f01aaa085cf7',
                        wait_until='domcontentloaded', timeout=30000)
        
        # Wait for AJAX
        await page.wait_for_timeout(15000)
        
        # Check page state
        info = await page.evaluate('''() => {
            let result = {};
            // Title
            let titleEl = document.getElementById('title');
            result.title_text = titleEl ? titleEl.innerText : 'no title el';
            
            // detail-new
            let detailEl = document.getElementById('detail-new');
            result.detail_text = detailEl ? detailEl.innerText.substring(0, 200) : 'no detail el';
            
            // All script tags
            result.scripts = [];
            document.querySelectorAll('script').forEach(s => {
                if (s.src) result.scripts.push(s.src);
                else if (s.textContent && s.textContent.length > 10) {
                    result.scripts.push('inline: ' + s.textContent.substring(0, 300));
                }
            });
            
            // Check if detail.js was loaded
            result.detail_js_loaded = Array.from(document.querySelectorAll('script')).some(s => s.src && s.src.includes('detail'));
            
            // All AJAX calls from performance entries
            if (window.performance) {
                result.entries = performance.getEntriesByType('resource').map(e => e.name).filter(n => n.includes('jcw'));
            }
            
            return result;
        }''')
        
        print('=== Detail page info ===')
        print(json.dumps(info, ensure_ascii=False, indent=2)[:3000])
        
        await browser.close()

asyncio.run(main())