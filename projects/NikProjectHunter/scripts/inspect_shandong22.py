"""Analyze captcha on Shandong ZFCG"""
import asyncio, json, base64
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        api_reqs = []
        page.on("request", lambda req: api_reqs.append({"url": req.url, "method": req.method}) if "captcha" in req.url.lower() or "verify" in req.url.lower() else None)
        
        await page.goto('http://www.ccgp-shandong.gov.cn/xxgk', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Click 采购公告
        for li in await page.query_selector_all("li"):
            text = await li.inner_text()
            if text.strip() == "采购公告":
                await li.click()
                await page.wait_for_timeout(2000)
                break
        
        # Check captcha details
        captcha_info = await page.evaluate("""
            () => {
                const el = document.querySelector('.n-captcha');
                if (!el) return 'not found';
                const img = el.querySelector('img');
                const input = el.querySelector('input');
                return {
                    img_src: img ? img.src : 'no img',
                    img_alt: img ? img.alt : '',
                    input_exists: !!input,
                    input_placeholder: input ? input.placeholder : '',
                    html: el.outerHTML.substring(0, 300),
                };
            }
        """)
        print("Captcha info:", json.dumps(captcha_info, ensure_ascii=False, indent=2))
        
        # Check captcha API calls
        print(f"\nCaptcha-related requests:")
        for r in api_reqs:
            print(f"  {r['method']} {r['url'][:80]}")
        
        # Check the captcha API
        captcha_api = await page.evaluate("""
            async () => {
                try {
                    const resp = await fetch('http://www.ccgp-shandong.gov.cn:8087/api/website/captcha');
                    const blob = await resp.blob();
                    const url = URL.createObjectURL(blob);
                    return {type: blob.type, size: blob.size, url: url.substring(0, 50)};
                } catch(e) {
                    return {error: e.message};
                }
            }
        """)
        print(f"\nCaptcha API test: {json.dumps(captcha_api, ensure_ascii=False)}")
        
        await browser.close()

asyncio.run(main())