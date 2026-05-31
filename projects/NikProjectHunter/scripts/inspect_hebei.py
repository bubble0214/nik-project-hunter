"""Inspect Hebei ZFCG site structure"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://www.ccgp-hebei.gov.cn/province/', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)
        
        print(f"Page title: {await page.title()}")
        
        # Find all links related to 采购公告/采购
        links = await page.eval_on_selector_all(
            "a[href*='cggg'], a[href*='cgzb'], a[href*='cgxx']",
            "els => els.map(e => ({href: e.href, text: e.innerText.trim().substring(0, 80)}))"
        )
        print(f"\nFound {len(links)} procurement links:")
        for l in links[:20]:
            print(f"  {l['text'][:50]:50s} -> {l['href'][:80]}")
        
        # Also check navigation
        nav_links = await page.eval_on_selector_all(
            "nav a, .nav a, [class*='nav'] a",
            "els => els.map(e => ({href: e.href, text: e.innerText.trim().substring(0, 50)}))"
        )
        print(f"\nNavigation links: {len(nav_links)}")
        for l in nav_links:
            print(f"  {l['text'][:40]:40s} -> {l['href'][:70]}")
        
        await browser.close()

asyncio.run(main())