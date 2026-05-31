"""
Docker 内测试 2：验证详情页访问 + 内容提取

确认 WAF bypass 后能否正常访问详情页并提取内容。
"""

import asyncio
import re
from pathlib import Path

DEBUG_DIR = Path("/app/debug/qlm_waf_test2")
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
        print(f"  [WARN] HTML save: {e}")
    try:
        await page.screenshot(path=str(png_path), full_page=False)
        print(f"  [OK] {label}.png saved")
    except Exception as e:
        print(f"  [WARN] Screenshot: {e}")


async def extract_detail(page, url: str) -> dict:
    """提取详情页信息"""
    result = {"url": url, "title": "", "content_len": 0, "buyer": None, "budget": None, "region": None, "publish_date": None}

    try:
        resp = await page.goto(url, wait_until="load", timeout=60000)
        print(f"  HTTP {resp.status if resp else 'N/A'}")
    except Exception as e:
        print(f"  ERROR goto: {e}")
        return result

    await asyncio.sleep(2)
    await save_snapshot(page, f"detail_{url.split('-')[-1].replace('.html','')}")

    # Title
    try:
        h1 = await page.query_selector("h1")
        if h1:
            result["title"] = (await h1.inner_text()).strip()
    except Exception:
        pass

    # Content
    try:
        body_text = await page.evaluate("document.body?.innerText || ''")
        result["content_len"] = len(body_text)
        # Extract buyer
        bm = re.search(r"招标[单人名][：:]\s*([^\s，,。.\n]{2,30})", body_text)
        if bm:
            result["buyer"] = bm.group(1).strip()
        # Extract budget
        bm2 = re.search(r"(?:预算|估价|金额|报价)[：:]\s*([\d,]+(?:\.\d+)?)", body_text)
        if bm2:
            result["budget"] = bm2.group(1)
        # Extract region
        rm = re.search(r"([\u4e00-\u9fff]{2,4}(?:省|市|区|县))", body_text)
        if rm:
            result["region"] = rm.group(1)
        # Extract date
        dm = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", body_text)
        if dm:
            result["publish_date"] = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
    except Exception as e:
        print(f"  ERROR extract: {e}")

    print(f"  Title: {result['title'][:60]}")
    print(f"  Content: {result['content_len']} chars")
    if result["buyer"]: print(f"  Buyer: {result['buyer']}")
    if result["budget"]: print(f"  Budget: {result['budget']}")
    if result["region"]: print(f"  Region: {result['region']}")
    if result["publish_date"]: print(f"  Date: {result['publish_date']}")

    return result


async def main():
    print("=" * 60)
    print("千里马详情页访问测试")
    print("=" * 60)

    async with async_playwright() as p:
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

        # STEP 1: 先访问首页过 WAF
        print("\n[STEP 1] 访问首页过 WAF ...")
        await page.goto("https://www.qianlima.com", wait_until="load", timeout=60000)
        await asyncio.sleep(5)
        await save_snapshot(page, "warmup_homepage")

        # STEP 2: 访问列表页
        print("\n[STEP 2] 访问列表页 ...")
        await page.goto("https://www.qianlima.com/zbgg/", wait_until="load", timeout=60000)
        await asyncio.sleep(3)
        await save_snapshot(page, "listpage")

        # 提取链接
        links = await page.query_selector_all("a[href*='bid-']")
        print(f"\n  找到 {len(links)} 个 bid 链接")

        # 过滤出有标题的链接
        candidates = []
        for link in links:
            title = (await link.inner_text()).strip()
            href = (await link.get_attribute("href") or "").strip()
            if title and len(title) > 5 and "bid-" in href:
                if href.startswith("//"):
                    href = "https:" + href
                elif href.startswith("/"):
                    href = "https://www.qianlima.com" + href
                candidates.append((title, href))

        print(f"  有效链接: {len(candidates)}")
        for i, (t, h) in enumerate(candidates[:8]):
            print(f"    [{i}] {t[:60]} | {h}")

        # STEP 3: 访问 3 个详情页（用新页面避免 cookie/context 过期）
        print("\n[STEP 3] 访问详情页（新页面）...")
        for i, (title, href) in enumerate(candidates[:3]):
            print(f"\n  --- 详情页 {i+1}: {title[:50]} ---")
            p2 = await context.new_page()
            try:
                await extract_detail(p2, href)
            finally:
                await p2.close()

        # STEP 4: 测试关键词过滤（查找数据安全相关标题）
        print("\n[STEP 4] 数据安全相关项目搜索 ...")
        keyword_tests = ["数据", "安全", "信息", "网络"]
        for kw in keyword_tests:
            matched = [(t, h) for t, h in candidates if kw in t]
            print(f"  关键词 '{kw}': 找到 {len(matched)} 个")
            if matched:
                for t, h in matched[:3]:
                    print(f"    {t[:60]}")

        await browser.close()

    print("\n" + "=" * 60)
    print("测试完成。检查 /app/debug/qlm_waf_test2/ 下的截图。")

if __name__ == "__main__":
    asyncio.run(main())