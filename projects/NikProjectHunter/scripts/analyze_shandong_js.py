"""Analyze Shandong main JS file"""
import httpx, re

r = httpx.get("http://www.ccgp-shandong.gov.cn/assets/index-CB3UPSvc.js", timeout=10)
content = r.text

# Find axios.create call
for m in re.finditer(r"\.create\s*\([^)]+\)", content):
    print(m.group()[:300])
print("---")
# Find any string containing 8087 or /api
for m in re.finditer(r"8087|/api/", content):
    start = max(0, m.start() - 80)
    end = min(len(content), m.end() + 80)
    print(content[start:end])
    print()