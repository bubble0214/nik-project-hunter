"""
Test Script: 千里马 WAF bypass test

测试 Playwright 完整浏览器能否通过华为云 WAF 的 JS Challenge。

测试策略：
1. 完整浏览器启动（非持久上下文）
2. 设置完整浏览器指纹（UA/Viewport/Locale/Timezone）
3. 等待 WAF JS Challenge 执行完毕（最多 30s）
4. 检测是否跳转到正常页面
5. 若跳转成功，尝试进入列表页和详情页
"""

import asyncio
import random
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

DEBUG_DIR = Path(__file__).resolve().parent.parent / "debug" / "qlm_waf_test"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


async def save_snapshot(page, label: str):
    html_path = DEBUG_DIR / f"{label}.html"
    png_path = DEBUG_DIR / f"{label}.png"
    try:
        html = await page.content()
        html_path.write_text(html, encoding="utf-8")
    except Exception as e:
        print(f"  [WARN] HTML save failed: {e}")
    try:
        await page.screenshot(path=str(png_path), full_page=False)
        print(f"  [OK] Screenshot saved: {png_path.name}")
    except Exception as e:
        print(f"  [WARN] Screenshot failed: {e}")


async def check_waf_result(page) -> dict:
    """检查页面是否通过了 WAF"""
    result = {"passed": False, "detected_by": [], "final_url": page.url}

    # 1. Check URL
    if "access" in page.url.lower() or "verify" in page.url.lower() or "waf" in page.url.lower():
        result["detected_by"].append("URL_contains_access_verify")

    # 2. Check title
    try:
        title = await page.title()
        if any(k in title for k in ["Access Verification", "验证", "验证码", "拦截"]):
            result["detected_by"].append(f"title_detected: {title}")
    except Exception:
        pass

    # 3. Check body content
    try:
        body_text = await page.evaluate("document.body?.innerText?.substring(0, 500) || ''")
        waf_signals = ["just a moment", "checking your browser", "access verification",
                       "安全验证", "请输入验证码", "滑动验证", "华为云WAF"]
        for sig in waf_signals:
            if sig.lower() in body_text.lower():
                result["detected_by"].append(f"body_signal: {sig}")
                break
    except Exception:
        pass

    # 4. Check if redirected to real content
    try:
        links = await page.query_selector_all("a[href*='bid-'], a[href*='zbgg'], a[href*='zhaobiao']")
        if len(links) > 3:
            result["detected_by"] = []  # clear WAF detections
            result["passed"] = True
            result["bid_links_found"] = len(links)
    except Exception:
        pass

    result["passed"] = len(result["detected_by"]) == 0
    return result


async def test_waf_bypass(ua_index: int = 0, headless: bool = False, extra_wait: int = 15):
    """测试 WAF bypass

    Args:
        ua_index: User-Agent 索引
        headless: 是否无头模式
        extra_wait: WAF JS 执行额外等待秒数
    """
    ua = USER_AGENTS[ua_index]
    label = f"headless_{headless}_ua{ua_index}_wait{extra_wait}"

    print(f"\n{'='*60}")
    print(f"测试: {label}")
    print(f"{'='*60}")
    print(f"  User-Agent: {ua[:60]}...")
    print(f"  Headless: {headless}")
    print(f"  Extra Wait: {extra_wait}s")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        )

        context = await browser.new_context(
            user_agent=ua,
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            },
        )

        # 反检测脚本（stealth）
        await context.add_init_script("""
            // Hide webdriver
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

            // Mock chrome object
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {},
                webstore: { onInstallStageChanged: {} }
            };

            // Overwrite permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications'
                    ? Promise.resolve({state: 'denied', onchange: null})
                    : originalQuery(parameters)
            );

            // Overwrite plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Overwrite languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });

            // Remove webdriver from navigator
            if (navigator.webdriver === false) {
                // Post data to check
            }
        """)

        page = await context.new_page()

        # 1. 先访问首页（可能会触发 WAF）
        print("  [STEP 1] 访问首页 https://www.qianlima.com ...")
        try:
            resp = await page.goto("https://www.qianlima.com", wait_until="load", timeout=60000)
            print(f"  [HTTP] Status: {resp.status if resp else 'N/A'}, URL: {page.url}")
        except Exception as e:
            print(f"  [ERROR] 首页访问失败: {type(e).__name__}")

        await asyncio.sleep(2)
        await save_snapshot(page, f"{label}_homepage")
        result = await check_waf_result(page)
        print(f"  [WAF] Passed: {result['passed']}")
        if not result["passed"]:
            print(f"  [WAF] Detected by: {result['detected_by']}")

        # 2. 等待 WAF JS Challenge 执行
        if extra_wait > 0:
            print(f"  [STEP 2] 等待 {extra_wait}s 让 WAF JS 执行完毕...")
            await asyncio.sleep(extra_wait)
            await save_snapshot(page, f"{label}_after_wait")
            result2 = await check_waf_result(page)
            print(f"  [WAF After Wait] Passed: {result2['passed']}")
            if not result2["passed"]:
                print(f"  [WAF] Detected by: {result2['detected_by']}")
            else:
                print(f"  [WAF] ✅ WAF bypass 成功！")

        # 3. 尝试访问列表页
        list_url = "https://www.qianlima.com/zbgg/"
        print(f"  [STEP 3] 访问列表页 {list_url} ...")
        try:
            resp = await page.goto(list_url, wait_until="load", timeout=60000)
            print(f"  [HTTP] Status: {resp.status if resp else 'N/A'}, URL: {page.url}")
        except Exception as e:
            print(f"  [ERROR] 列表页访问失败: {type(e).__name__}")

        await asyncio.sleep(3)
        await save_snapshot(page, f"{label}_listpage")
        result3 = await check_waf_result(page)
        print(f"  [WAF] Passed: {result3['passed']}")
        if result3.get("bid_links_found"):
            print(f"  [OK] 找到 {result3['bid_links_found']} 个 bid 链接")
        if not result3["passed"]:
            print(f"  [WAF] Detected by: {result3['detected_by']}")
        else:
            print(f"  [WAF] ✅ 列表页通过！")

        # 4. 尝试提取列表页的链接
        if result3["passed"]:
            print("  [STEP 4] 提取链接...")
            try:
                bid_links = await page.query_selector_all("a[href*='bid-']")
                print(f"  [OK] a[href*='bid-']: {len(bid_links)}")
                for i, link in enumerate(bid_links[:5]):
                    title = (await link.inner_text()).strip()[:80]
                    href = await link.get_attribute("href")
                    print(f"    [{i}] {title} | {href}")
            except Exception as e:
                print(f"  [ERROR] 链接提取: {e}")

        await browser.close()

    return result3


async def main():
    print("=" * 60)
    print("千里马 WAF Bypass 测试")
    print("=" * 60)

    # 测试组合
    tests = [
        # (headless, extra_wait)
        (False, 10),   # 有头模式 + 10s 等待
        (False, 20),   # 有头模式 + 20s 等待
    ]

    for i, (headless, wait) in enumerate(tests):
        result = await test_waf_bypass(ua_index=0, headless=headless, extra_wait=wait)
        if result["passed"]:
            print(f"\n{'='*60}")
            print("🎉 WAF Bypass 成功！")
            print(f"{'='*60}")
            break
        else:
            print(f"\n{'='*60}")
            print(f"❌ 测试组合 {i} 失败")
            print(f"{'='*60}")
            # 如果第一个组合失败了，继续下一个

    print("\n测试完成。检查 debug/qlm_waf_test/ 下的截图和 HTML。")

if __name__ == "__main__":
    asyncio.run(main())