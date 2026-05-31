"""
测试中国政府采购网搜索 — 使用不同参数避免反爬
"""
import sys, os, json, asyncio
sys.path.insert(0, '/app')
os.environ.setdefault('APP_ENV', 'development')

from playwright.async_api import async_playwright
from urllib.parse import quote

async def test():
    # 使用更简单的参数
    keyword = "数据分类分级"
    url = f"http://search.ccgp.gov.cn/bxsearch?searchtype=1&page_index=1&keyword={quote(keyword)}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 模拟正常浏览器
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )
        page = await context.new_page()
        
        # 先访问首页
        await page.goto("http://www.ccgp.gov.cn/", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
        print(f"首页加载完成: {await page.title()}")
        
        # 再搜索
        print(f"\n搜索 URL: {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)
        
        body_text = await page.evaluate("document.body?.innerText || ''")
        print(f"页面标题: {await page.title()}")
        print(f"页面文本长度: {len(body_text)}")
        
        if "频繁访问" in body_text:
            print("❌ 触发反爬!")
        else:
            print("✅ 正常访问!")
            results = await page.query_selector_all("a[target='_blank']")
            print(f"搜索结果链接数: {len(results)}")
            for i, r in enumerate(results[:15]):
                title = (await r.inner_text()).strip()
                href = (await r.get_attribute("href") or "")[:80]
                print(f"  [{i+1}] {title[:60]}")
        
        await browser.close()

asyncio.run(test())