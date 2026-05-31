"""
Docker 内测试：千里马 WAF bypass

直接在容器内用 Playwright 测试能否通过华为云 WAF。
"""

import asyncio
import sys
from pathlib import Path

DEBUG_DIR = Path("/app/debug/qlm_waf_test")
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

from playwright.async_api import async_playwright


async def save_snapshot(page, label: str):
    html_path = DEBUG_DIR / f"{label}.html"
    png_path = DEBUG_DIR / f"{label}.png"
    try:
        html = await page.content()
        html_path.write_text(html, encoding="utf-8")
        print(f"  [OK] {label}.html saved")
    except Exception as e:
        print(f"  [WARN] HTML save failed: {e}")
    try:
        await page.screenshot(path=str(png_path), full_page=False)
        print(f"  [OK] {label}.png saved")
    except Exception as e:
        print(f"  [WARN] Screenshot failed: {e}")


async def check_waf(page) -> dict:
    """检查页面是否被 WAF 拦截"""
    result = {"passed": False, "reason": [], "url": page.url}
    try:
        title = await page.title()
        body = await page.evaluate("document.body?.innerText?.substring(0, 1000) || ''")
        html = await page.content()
    except Exception as e:
        result["reason"].append(f"page_error: {e}")
        return result

    # Check signals
    signals = {
        "title": title,
        "body": body,
        "html_head": html[:500],
    }

    waf_keywords = [
        "Access Verification", "just a moment", "checking your browser",
        "安全验证", "验证码", "滑动验证", "华为云WAF", "Access denied",
        "请输入验证码", "人机验证", "verify", "challenge",
    ]

    for key, text in signals.items():
        for kw in waf_keywords:
            if kw.lower() in text.lower():
                result["reason"].append(f"{key}: {kw}")
                break

    # Check for bid links (real content)
    try:
        bid_links = await page.query_selector_all("a[href*='bid-'], a[href*='zbgg'], a[href*='zhaobiao'], a[href*='detail']")
        if len(bid_links) > 3:
            result["reason"] = []  # clear WAF signals
            result["passed"] = True
            result["bid_count"] = len(bid_links)
    except Exception:
        pass

    result["passed"] = len(result["reason"]) == 0
    return result


async def main():
    print("=" * 60)
    print("Docker 内千里马 WAF Bypass 测试")
    print("=" * 60)

    async with async_playwright() as p:
        # 测试 1: 无头模式 + 标准 stealth
        print("\n[TEST 1] 无头模式 + stealth")
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
        """)

        page = await context.new_page()

        # 访问首页
        print("  访问 https://www.qianlima.com ...")
        try:
            resp = await page.goto("https://www.qianlima.com", wait_until="load", timeout=60000)
            print(f"  HTTP {resp.status if resp else 'N/A'}, URL: {page.url}")
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")

        await asyncio.sleep(2)
        await save_snapshot(page, "test1_homepage")
        r1 = await check_waf(page)
        print(f"  WAF passed: {r1['passed']}")
        if not r1["passed"]:
            print(f"  Reason: {r1['reason']}")

        # 等待更长看看 WAF JS Challenge 是否完成
        print("  等待 15s 让 WAF JS 执行...")
        await asyncio.sleep(15)
        await save_snapshot(page, "test1_after_15s")
        r1b = await check_waf(page)
        print(f"  WAF passed after 15s: {r1b['passed']}")
        if r1b["passed"]:
            print(f"  ✅ 找到 {r1b.get('bid_count', 0)} 个 bid 链接")
        else:
            print(f"  Reason: {r1b['reason']}")

        # 访问列表页
        print("  访问列表页 https://www.qianlima.com/zbgg/ ...")
        try:
            resp = await page.goto("https://www.qianlima.com/zbgg/", wait_until="load", timeout=60000)
            print(f"  HTTP {resp.status if resp else 'N/A'}, URL: {page.url}")
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")

        await asyncio.sleep(3)
        await save_snapshot(page, "test1_listpage")
        r2 = await check_waf(page)
        print(f"  WAF passed: {r2['passed']}")
        if r2["passed"]:
            print(f"  ✅ 找到 {r2.get('bid_count', 0)} 个链接")
            # 提取具体链接
            try:
                links = await page.query_selector_all("a[href*='bid-']")
                for i, l in enumerate(links[:5]):
                    t = (await l.inner_text()).strip()[:80]
                    h = await l.get_attribute("href")
                    print(f"    [{i}] {t} | {h}")
            except Exception as e:
                print(f"  提取链接失败: {e}")
        else:
            print(f"  Reason: {r2['reason']}")

        await browser.close()

        # 如果测试1失败，测试2：换 UA + 更长的等待
        if not r2["passed"]:
            print("\n[TEST 2] 不同 UA + 30s 等待")
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ]
            )

            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                extra_http_headers={
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )

            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications'
                        ? Promise.resolve({state: 'denied', onchange: null})
                        : originalQuery(parameters)
                );
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            """)

            page = await context.new_page()

            print("  访问 https://www.qianlima.com ...")
            try:
                resp = await page.goto("https://www.qianlima.com", wait_until="load", timeout=60000)
                print(f"  HTTP {resp.status if resp else 'N/A'}, URL: {page.url}")
            except Exception as e:
                print(f"  ERROR: {type(e).__name__}: {e}")

            await asyncio.sleep(2)
            await save_snapshot(page, "test2_homepage")
            r = await check_waf(page)
            print(f"  WAF passed: {r['passed']}")
            if not r["passed"]:
                print(f"  Reason: {r['reason']}")

            print("  等待 30s...")
            await asyncio.sleep(30)
            await save_snapshot(page, "test2_after_30s")
            r = await check_waf(page)
            print(f"  WAF after 30s: {r['passed']}")
            if r["passed"]:
                print(f"  ✅ 找到 {r.get('bid_count', 0)} 个链接")
            else:
                print(f"  Reason: {r['reason']}")

            print("  访问列表页...")
            try:
                resp = await page.goto("https://www.qianlima.com/zbgg/", wait_until="load", timeout=60000)
                print(f"  HTTP {resp.status if resp else 'N/A'}, URL: {page.url}")
            except Exception as e:
                print(f"  ERROR: {type(e).__name__}: {e}")

            await asyncio.sleep(5)
            await save_snapshot(page, "test2_listpage")
            r = await check_waf(page)
            print(f"  WAF passed: {r['passed']}")
            if r["passed"]:
                print(f"  ✅ 找到 {r.get('bid_count', 0)} 个链接")
            else:
                print(f"  Reason: {r['reason']}")

            await browser.close()

    print("\n" + "=" * 60)
    print("测试完成。检查 /app/debug/qlm_waf_test/ 下的截图和 HTML。")

if __name__ == "__main__":
    asyncio.run(main())