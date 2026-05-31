"""Extract Shandong announcements via Playwright page rendering"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Navigate to home and wait for all content to render
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        # Extract all visible announcement items from the rendered page
        # They are in the 采购信息 section
        announcements = await page.evaluate("""
            () => {
                const items = [];
                // Find all announcement-like elements
                // They appear as structured items with title + date
                const allElements = document.querySelectorAll('*');
                
                for (const el of allElements) {
                    const text = el.innerText?.trim();
                    // Look for items with date pattern at end
                    if (text && text.length > 15 && text.length < 200) {
                        const hasDate = /\\d{4}[-/]\\d{1,2}[-/]\\d{1,2}/.test(text);
                        if (hasDate && /采购|招标|公告|磋商|谈判|询价/.test(text)) {
                            items.push(text);
                        }
                    }
                }
                return [...new Set(items)];
            }
        """)
        
        print(f"Found {len(announcements)} announcements:")
        for a in announcements[:30]:
            print(f"  {a}")
        
        # Also try to find the detail page URL pattern
        # Check if clicking on items opens a new page
        print("\nTrying to click on first announcement...")
        
        # Find clickable elements containing announcement text
        clickable = await page.evaluate("""
            () => {
                const items = [];
                // Look for elements with onclick or that trigger navigation
                const all = document.querySelectorAll('[onclick], [href], [data-id], [data-url], .pointer, [style*=\"cursor\"]');
                for (const el of all) {
                    const text = el.innerText?.trim();
                    if (text && text.length > 15 && /\\d{4}[-/]\\d{1,2}[-/]\\d{1,2}/.test(text)) {
                        items.push({
                            text: text.substring(0, 80),
                            onclick: (el.getAttribute('onclick') || '').substring(0, 100),
                            href: el.href || '',
                            dataId: el.getAttribute('data-id') || el.getAttribute('data-url') || '',
                            tag: el.tagName,
                            className: (el.className || '').substring(0, 80),
                        });
                    }
                }
                return items;
            }
        """)
        
        print(f"\nClickable items: {len(clickable)}")
        for c in clickable[:10]:
            print(f"  {json.dumps(c, ensure_ascii=False)}")
        
        await browser.close()

asyncio.run(main())