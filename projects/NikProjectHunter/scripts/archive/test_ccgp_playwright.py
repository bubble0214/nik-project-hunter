"""Test China ZFCG page with Playwright"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('http://www.ccgp.gov.cn/cggg/zygg/gkzb/', timeout=30000, wait_until='networkidle')
    page.wait_for_timeout(5000)
    # Get all links using query_selector_all
    links = page.query_selector_all('a')
    print('Total links:', len(links))
    count = 0
    for a in links:
        href = a.get_attribute('href') or ''
        text = (a.inner_text() or '').strip()[:50]
        if '/cggg/' in href or 't202' in href:
            print('  ', text, ' -> ', href[:90])
            count += 1
            if count >= 20:
                break
    print('---')
    # Also check the page title
    print('Title:', page.title())
    browser.close()