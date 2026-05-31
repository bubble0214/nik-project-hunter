"""Get captcha image via page evaluate (in-browser fetch)"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        await page.goto('http://www.ccgp-shandong.gov.cn/xxgk', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Get captcha image as base64 from inside the page
        result = await page.evaluate("""
            async () => {
                try {
                    const resp = await fetch('http://www.ccgp-shandong.gov.cn:8087/api/website/captcha');
                    const blob = await resp.blob();
                    const captchaUuid = resp.headers.get('captcha-uuid');
                    
                    // Convert blob to base64
                    return new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onloadend = () => resolve({
                            success: true,
                            base64: reader.result,
                            captchaUuid: captchaUuid,
                            contentType: blob.type,
                            size: blob.size,
                        });
                        reader.onerror = () => reject({error: 'FileReader failed'});
                        reader.readAsDataURL(blob);
                    });
                } catch(e) {
                    return {error: e.message, stack: e.stack};
                }
            }
        """)
        
        print("Result keys:", list(result.keys()))
        if result.get("success"):
            print(f"Captcha UUID: {result.get('captchaUuid')}")
            print(f"Content type: {result.get('contentType')}")
            print(f"Size: {result.get('size')}")
            b64 = result.get("base64", "")
            print(f"Base64 length: {len(b64)}")
            
            # Save the image
            import base64
            img_data = base64.b64decode(b64.split(",")[1] if "," in b64 else b64)
            with open("/app/debug/shandong_captcha.png", "wb") as f:
                f.write(img_data)
            print("Saved captcha image")
        else:
            print(f"Error: {result.get('error')}")
            print(f"Stack: {result.get('stack','')[:200]}")
        
        await browser.close()

asyncio.run(main())