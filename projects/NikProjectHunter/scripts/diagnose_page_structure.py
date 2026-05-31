"""
诊断中国政府采购网页面结构
"""
import sys, os, json, asyncio
sys.path.insert(0, '/app')
os.environ.setdefault('APP_ENV', 'development')

from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 访问中央公开招标页面
        url = "http://www.ccgp.gov.cn/cggg/zygg/gkzb/"
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)
        
        print(f"URL: {page.url}")
        print(f"Title: {await page.title()}")
        
        # 获取所有链接
        links = await page.evaluate("""() => {
            const allLinks = document.querySelectorAll('a');
            const results = [];
            allLinks.forEach(a => {
                const href = a.getAttribute('href') || '';
                const text = (a.innerText || '').trim();
                if (text && text.length > 5 && href) {
                    results.push({text: text.substring(0, 60), href: href.substring(0, 100)});
                }
            });
            return results;
        }""")
        
        print(f"\n所有包含文本的链接 ({len(links)}):")
        for l in links:
            print(f"  text='{l['text']}' href='{l['href']}'")
        
        # 获取页面 HTML 结构
        structure = await page.evaluate("""() => {
            const body = document.body;
            const walker = document.createTreeWalker(body, NodeFilter.SHOW_ELEMENT);
            const tags = {};
            while(walker.nextNode()) {
                const node = walker.currentNode;
                const tag = node.tagName.toLowerCase();
                const cls = node.className || '';
                const key = tag + (cls ? '.' + cls.substring(0,30) : '');
                tags[key] = (tags[key] || 0) + 1;
            }
            return Object.entries(tags).sort((a,b) => b[1]-a[1]).slice(0, 30);
        }""")
        
        print(f"\n页面结构 (前30):")
        for k, v in structure:
            print(f"  <{k}> x{v}")
        
        await browser.close()

asyncio.run(test())