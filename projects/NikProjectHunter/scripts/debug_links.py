"""
调试中国政府采购网 /cggg/ 页面 — 查看链接结构
"""
import sys, os, json, asyncio
sys.path.insert(0, '/app')
os.environ.setdefault('APP_ENV', 'development')

from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        
        # 先访问首页获取 cookie
        await page.goto("http://www.ccgp.gov.cn/", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
        print(f"首页 Title: {await page.title()}")
        
        # 再访问公告页
        await page.goto("http://www.ccgp.gov.cn/cggg/", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        
        print(f"公告页 Title: {await page.title()}")
        
        # 获取所有链接的 href 和文本
        links = await page.evaluate("""() => {
            const allLinks = document.querySelectorAll('a');
            const results = [];
            allLinks.forEach(a => {
                let href = a.getAttribute('href') || '';
                let text = (a.innerText || '').trim();
                if (text.length > 5 && href) {
                    results.push({text: text.substring(0, 80), href: href.substring(0, 120)});
                }
            });
            return results;
        }""")
        
        print(f"\n所有链接 ({len(links)}):")
        for l in links:
            print(f"  [{l['text'][:60]}] -> {l['href'][:100]}")
        
        # 检查包含 cggg 的链接
        print(f"\n包含 cggg 的链接:")
        for l in links:
            if 'cggg' in l['href']:
                print(f"  [{l['text'][:60]}] -> {l['href'][:100]}")
        
        await browser.close()

asyncio.run(test())