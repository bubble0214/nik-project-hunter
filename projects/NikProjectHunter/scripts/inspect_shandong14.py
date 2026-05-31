"""Try direct navigation to Shandong announcement pages"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Try to navigate directly to the announcement listing page
        # The site is built with Vue Router, likely has routes like /notice or /xxgk
        urls_to_try = [
            'http://www.ccgp-shandong.gov.cn/xxgk',
            'http://www.ccgp-shandong.gov.cn/xxgk/',
            'http://www.ccgp-shandong.gov.cn/home/xxgk',
            'http://www.ccgp-shandong.gov.cn/notice',
            'http://www.ccgp-shandong.gov.cn/announce',
            'http://www.ccgp-shandong.gov.cn/cggg',
            'http://www.ccgp-shandong.gov.cn/purchase',
            'http://www.ccgp-shandong.gov.cn/#/xxgk',
            'http://www.ccgp-shandong.gov.cn/home#/xxgk',
            'http://www.ccgp-shandong.gov.cn/home/announce',
        ]
        
        for url in urls_to_try:
            print(f"\nTrying: {url}")
            try:
                resp = await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                await page.wait_for_timeout(3000)
                title = await page.title()
                body = await page.evaluate("document.body.innerText.substring(0, 200)")
                print(f"  Title: {title}")
                print(f"  Body: {body[:150]}")
                
                # Check for announcements
                links = await page.evaluate("""
                    () => {
                        const items = [];
                        document.querySelectorAll('a[href]').forEach(el => {
                            const text = el.innerText?.trim();
                            if (text && text.length > 20 && /(采购|招标|磋商|谈判|公告)/.test(text)) {
                                items.push({text: text.substring(0, 60), href: el.href.substring(0, 80)});
                            }
                        });
                        return items.slice(0, 5);
                    }
                """)
                if links:
                    print(f"  Announcements: {len(links)}")
                    for l in links[:3]:
                        print(f"    {l['text'][:40]} -> {l['href'][:40]}")
            except Exception as e:
                print(f"  Error: {str(e)[:50]}")
        
        await browser.close()

asyncio.run(main())