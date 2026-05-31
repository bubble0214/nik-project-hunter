"""Test captcha API and try OCR approach"""
import asyncio, httpx
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        await page.goto('http://www.ccgp-shandong.gov.cn/xxgk', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Get captcha image via Playwright's request context
        resp = await page.request.get("http://www.ccgp-shandong.gov.cn:8087/api/website/captcha")
        print(f"Captcha status: {resp.status}")
        print(f"Headers: {dict(resp.headers)}")
        
        body = await resp.body()
        print(f"Body size: {len(body)}")
        
        if len(body) > 100:
            # Save the captcha image
            with open("/app/debug/shandong_captcha.png", "wb") as f:
                f.write(body)
            print("Saved captcha to /app/debug/shandong_captcha.png")
        
        await browser.close()

asyncio.run(main())