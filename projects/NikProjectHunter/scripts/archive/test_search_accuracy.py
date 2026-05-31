"""
测试中国政府采购网搜索结果 — 查看搜索词是否有效
"""
import sys, os, json, asyncio
sys.path.insert(0, '/app')
os.environ.setdefault('APP_ENV', 'development')

from playwright.async_api import async_playwright
from urllib.parse import quote

async def test():
    # 直接搜索并查看搜索结果
    keyword = "数据分类分级"
    url = f"http://search.ccgp.gov.cn/bxsearch?searchtype=1&page_index=1&keyword={quote(keyword)}&dbselect=bxall&time_type=6"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)
        
        # 查看页面内容
        body_text = await page.evaluate("document.body?.innerText || ''")
        print(f"页面标题: {await page.title()}")
        print(f"页面文本长度: {len(body_text)}")
        
        # 查看搜索结果区域
        results = await page.query_selector_all("a[target='_blank']")
        print(f"搜索结果链接数: {len(results)}")
        
        # 检查搜索关键词是否出现在页面中
        kw_in_page = keyword in body_text
        print(f"搜索关键词 '{keyword}' 是否在页面中: {kw_in_page}")
        
        # 列出前几个结果
        print("\n前10个结果:")
        for i, r in enumerate(results[:10]):
            title = (await r.inner_text()).strip()
            href = (await r.get_attribute("href") or "")[:80]
            print(f"  [{i+1}] {title[:60]} -> {href}")
        
        await browser.close()

asyncio.run(test())