"""Find intent links on China ZFCG"""
import httpx, re

r = httpx.get("http://www.ccgp.gov.cn/", timeout=10)
html = r.text

for m in re.finditer(r"意向", html):
    start = max(0, m.start() - 200)
    end = min(len(html), m.end() + 50)
    print(html[start:end])
    print("---")