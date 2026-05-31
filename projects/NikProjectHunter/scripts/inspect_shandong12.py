"""Playwright full browser approach for Shandong ZFCG"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        )
        page = await context.new_page()
        
        # Stealth: override webdriver
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("Navigating to home...")
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=60000)
        print("Waiting for page to render...")
        await page.wait_for_timeout(8000)
        
        # Check what rendered
        title = await page.title()
        print(f"Title: {title}")
        
        body_text = await page.evaluate("document.body.innerText.substring(0, 200)")
        print(f"Body text: {body_text}")
        
        # Try to find any announcement elements
        elements = await page.evaluate("""
            () => {
                const items = [];
                // Look for links or divs containing announcement info
                document.querySelectorAll('a, li, div.item, div.list-item, .announcement, [class*="gg"], [class*="notice"]').forEach(el => {
                    const text = el.innerText?.trim();
                    if (text && text.length > 15 && /(采购|招标|公告|磋商|谈判|询价|意向)/.test(text)) {
                        items.push({
                            text: text.substring(0, 100),
                            tag: el.tagName,
                            class: (el.className || '').substring(0, 60),
                            href: el.href || '',
                        });
                    }
                });
                return items.slice(0, 20);
            }
        """)
        
        print(f"\nFound {len(elements)} announcement-like elements:")
        for el in elements[:10]:
            print(f"  [{el['tag']}.{el['class']}] {el['text'][:60]} | href={el['href'][:60]}")
        
        # Get all visible text
        all_text = await page.evaluate("document.body.innerText")
        print(f"\nTotal visible text length: {len(all_text)}")
        print(f"First 500 chars: {all_text[:500]}")
        
        await browser.close()

asyncio.run(main())