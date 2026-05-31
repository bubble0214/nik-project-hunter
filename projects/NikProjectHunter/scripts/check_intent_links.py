"""Find 采购意向 URLs for Tianjin, Hebei, China ZFCG"""
import asyncio
from playwright.async_api import async_playwright

async def check_tianjin(page):
    print("=== 天津市政府采购网 ===")
    await page.goto('http://tjgp.cz.tj.gov.cn/', wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(2000)
    
    # Get all links from the page
    links = await page.eval_on_selector_all("a[href]", "els => els.map(e => ({href: e.href, text: e.innerText.trim().substring(0, 50)}))")
    
    # Find 采购意向
    intent = [l for l in links if '意向' in l['text'] or 'cgyx' in l['href']]
    print(f"  采购意向 links ({len(intent)}):")
    for l in intent:
        print(f"    {l['text'][:40]:40s} -> {l['href'][:80]}")
    
    # Try to click on 采购意向公开 in sidebar
    sidebar_links = await page.query_selector_all("a[href*='cgyx']")
    for a in sidebar_links:
        href = await a.get_attribute("href")
        text = await a.inner_text()
        print(f"    Sidebar: {text.strip()[:40]} -> {href[:80]}")

async def check_hebei(page):
    print("\n=== 河北省政府采购网 ===")
    await page.goto('https://www.ccgp-hebei.gov.cn/province/', wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(3000)
    
    links = await page.eval_on_selector_all("a[href]", "els => els.map(e => ({href: e.href, text: e.innerText.trim().substring(0, 50)}))")
    intent = [l for l in links if '意向' in l['text'] or 'yxtk' in l['href'].lower()]
    print(f"  采购意向 links ({len(intent)}):")
    for l in intent:
        print(f"    {l['text'][:40]:40s} -> {l['href'][:80]}")

async def check_china_zfcg(page):
    print("\n=== 中国政府采购网 ===")
    await page.goto('http://www.ccgp.gov.cn/', wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(2000)
    
    links = await page.eval_on_selector_all("a[href]", "els => els.map(e => ({href: e.href, text: e.innerText.trim().substring(0, 50)}))")
    intent = [l for l in links if '意向' in l['text']]
    print(f"  采购意向 links ({len(intent)}):")
    for l in intent:
        print(f"    {l['text'][:40]:40s} -> {l['href'][:80]}")

async def check_jincai(page):
    print("\n=== 金采网 ===")
    await page.goto('http://www.cfcpn.com/jcw', wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(3000)
    
    links = await page.eval_on_selector_all("a[href]", "els => els.map(e => ({href: e.href, text: e.innerText.trim().substring(0, 50)}))")
    intent = [l for l in links if '意向' in l['text'] or '采购预告' in l['text']]
    print(f"  采购意向/预告 links ({len(intent)}):")
    for l in intent:
        print(f"    {l['text'][:40]:40s} -> {l['href'][:80]}")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        page = await context.new_page()
        await check_tianjin(page)
        
        page2 = await context.new_page()
        await check_hebei(page2)
        
        page3 = await context.new_page()
        await check_china_zfcg(page3)
        
        page4 = await context.new_page()
        await check_jincai(page4)
        
        await browser.close()

asyncio.run(main())