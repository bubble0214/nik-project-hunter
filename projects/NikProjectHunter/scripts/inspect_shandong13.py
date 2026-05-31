"""Click through Shandong ZFCG to load announcements"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("Navigating...")
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Click on 采购信息 section to expand
        print("\nLooking for 采购信息...")
        buttons = await page.query_selector_all("button, .el-button, [class*='button'], [role='button'], .el-collapse-item__header, div[class*='header'], span")
        for btn in buttons:
            text = await btn.inner_text()
            if '采购信息' in text.strip():
                print(f"Found 采购信息 button: {text.strip()[:30]}")
                await btn.click()
                await page.wait_for_timeout(2000)
                break
        
        # Now look for 采购公告
        print("\nLooking for 采购公告...")
        for selector in ["a", "span", "li", "div[class*='item']", "div[class*='title']"]:
            elements = await page.query_selector_all(selector)
            for el in elements:
                text = await el.inner_text()
                if '采购公告' in text.strip():
                    print(f"Found 采购公告: {text.strip()[:30]} | tag={await el.evaluate('e => e.tagName')}")
                    await el.click()
                    await page.wait_for_timeout(3000)
                    break
            else:
                continue
            break
        
        # Check what loaded
        body = await page.evaluate("document.body.innerText")
        print(f"\nBody after clicking: {body[:1000]}")
        
        # Look for announcement list
        links = await page.evaluate("""
            () => {
                const items = [];
                document.querySelectorAll('a[href]').forEach(el => {
                    const text = el.innerText?.trim();
                    if (text && text.length > 20 && /(采购|招标|磋商|谈判|询价|公告)/.test(text)) {
                        items.push({text: text.substring(0, 80), href: el.href.substring(0, 100)});
                    }
                });
                return items.slice(0, 30);
            }
        """)
        print(f"\nAnnouncement links: {len(links)}")
        for l in links[:10]:
            print(f"  {l['text'][:60]} | {l['href'][:60]}")
        
        # Try 意向公开
        print("\n\nLooking for 意向公开...")
        spans = await page.query_selector_all("span, a, div[class*='item']")
        for el in spans:
            text = await el.inner_text()
            if '意向公开' in text.strip():
                print(f"Found 意向公开: {text.strip()[:30]}")
                await el.click()
                await page.wait_for_timeout(3000)
                intent_body = await page.evaluate("document.body.innerText")
                print(f"Intent area: {intent_body[500:1000]}")
                break
        
        await browser.close()

asyncio.run(main())