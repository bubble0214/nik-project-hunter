"""Inspect Shandong ZFCG site structure"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('http://www.ccgp-shandong.gov.cn/home', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        print(f"Page title: {await page.title()}")
        
        # All links
        links = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({href: e.href, text: e.innerText.trim().substring(0, 60)}))"
        )
        print(f"\nAll links ({len(links)}):")
        for l in links[:30]:
            print(f"  {l['text'][:50]:50s} -> {l['href'][:80]}")
        
        # Check for procurement links
        procurement = [l for l in links if any(k in l['text'] for k in ['采购', '招标', '公告', '数据', '平台', '系统'])]
        print(f"\nProcurement related ({len(procurement)}):")
        for l in procurement[:20]:
            print(f"  {l['text'][:50]:50s} -> {l['href'][:80]}")
        
        await browser.close()

asyncio.run(main())