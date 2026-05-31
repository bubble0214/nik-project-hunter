"""
诊断中国政府采购网首页结构
"""
import sys, os, json, asyncio
sys.path.insert(0, '/app')
os.environ.setdefault('APP_ENV', 'development')

from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # 尝试首页
        for url in [
            "http://www.ccgp.gov.cn/",
            "http://www.ccgp.gov.cn/cggg/",
        ]:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)
                
                print(f"\n{'='*60}")
                print(f"URL: {url}")
                print(f"Title: {await page.title()}")
                
                body_text = await page.evaluate("document.body?.innerText?.substring(0,1000) || ''")
                if "403" in body_text or "Forbidden" in body_text:
                    print("❌ 403 Forbidden")
                else:
                    print(f"页面文本 (前500): {body_text[:500]}")
                    
                    # 获取所有有意义的链接
                    links = await page.evaluate("""() => {
                        const allLinks = document.querySelectorAll('a');
                        const results = [];
                        allLinks.forEach(a => {
                            const href = a.getAttribute('href') || '';
                            const text = (a.innerText || '').trim();
                            if (text.length > 8 && href) {
                                results.push({text: text.substring(0, 60), href: href.substring(0, 100)});
                            }
                        });
                        return results;
                    }""")
                    
                    print(f"\n公告链接 ({len(links)}):")
                    for l in links[:20]:
                        print(f"  text='{l['text']}' href='{l['href']}'")
            except Exception as e:
                print(f"❌ {url}: {e}")
        
        await browser.close()

asyncio.run(test())