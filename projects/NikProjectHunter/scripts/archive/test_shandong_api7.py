"""Try API via main domain proxy"""
import httpx, json

headers = {
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "http://www.ccgp-shandong.gov.cn",
    "Referer": "http://www.ccgp-shandong.gov.cn/home",
    "X-Requested-With": "XMLHttpRequest",
}

payload = {
    "colCode": "0301",
    "area": "370000",
    "currentPage": 1,
    "pageSize": 50,
    "homePage": 0,
    "mergeType": 0,
    "cityType": 1,
}

# Try via main domain (nginx proxy)
r = httpx.post(
    "http://www.ccgp-shandong.gov.cn/website/site/getListByCode",
    json=payload,
    headers=headers,
    timeout=15,
)

print("Status:", r.status_code)
print("URL:", r.url)
try:
    data = r.json()
    print("Success:", data.get("success"))
    items = data.get("data", {}).get("data", [])
    print("Items:", len(items))
    for item in items[:5]:
        print(f"\n  Title: {item.get('title','')[:60]}")
        print(f"  Date: {item.get('createDate','')}")
        print(f"  ID: {item.get('id','')}")
        print(f"  Area: {item.get('areaName','')}")
except Exception as e:
    print(f"Parse error: {e}")
    print(f"Response: {r.text[:500]}")