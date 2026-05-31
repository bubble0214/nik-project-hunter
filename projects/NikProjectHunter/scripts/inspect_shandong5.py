"""Find Shandong ZFCG announcement detail page structure"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        # Get all announcement list items using JS evaluation
        # They are in the 采购信息 section
        items = await page.evaluate("""
            () => {
                // Find the procurement section
                const sections = document.querySelectorAll('.section, .module, [class*=info], [class*=procurement]');
                const results = [];
                
                // Look for announcement items
                const allLinks = document.querySelectorAll('a');
                for (const a of allLinks) {
                    const text = a.innerText.trim();
                    const href = a.href;
                    if (text.length > 15 && href && href !== 'javascript:void(0)') {
                        results.push({text: text.substring(0, 80), href: href.substring(0, 150)});
                    }
                }
                return results;
            }
        """)
        
        print(f"All non-void links with text > 15 chars: {len(items)}")
        for item in items[:20]:
            print(f"  {item['text'][:60]:60s} -> {item['href'][:100]}")
        
        # Also try to find detail page links (those that open announcements)
        detail_links = await page.evaluate("""
            () => {
                const links = [];
                document.querySelectorAll('a[href*="xxgk"], a[href*="bulletin"], a[href*="notice"], a[onclick]').forEach(a => {
                    links.push({
                        text: a.innerText.trim().substring(0, 80),
                        href: a.href,
                        onclick: (a.getAttribute('onclick') || '').substring(0, 100)
                    });
                });
                return links;
            }
        """)
        print(f"\nDetail links: {len(detail_links)}")
        for dl in detail_links[:10]:
            print(f"  text={dl['text'][:50]} | href={dl['href'][:80]} | onclick={dl['onclick'][:80]}")
        
        # Try clicking on one of the 采购公告 items
        # First try to click "采购公告" tab to switch to it
        tabs = await page.query_selector_all("text=采购公告")
        print(f"\n采购公告 tab elements: {len(tabs)}")
        
        await browser.close()

asyncio.run(main())