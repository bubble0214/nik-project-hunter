"""Try API with proper headers"""
import httpx, json

headers = {
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "http://www.ccgp-shandong.gov.cn",
    "Referer": "http://www.ccgp-shandong.gov.cn/home",
}

payload = {
    "colCode": "0301",
    "area": "370000",
    "currentPage": 1,
    "pageSize": 12,
    "homePage": 1,
    "mergeType": 0,
    "cityType": 1,
}

r = httpx.post(
    "http://www.ccgp-shandong.gov.cn:8087/api/website/site/getListByCode",
    json=payload,
    headers=headers,
    timeout=15,
)

print("Status:", r.status_code)
print("Headers:", dict(r.headers))
data = r.json()
print("Success:", data.get("success"))
items = data.get("data", {}).get("data", [])
print("Items:", len(items))

if items:
    for item in items[:5]:
        print(f"\n--- Item ---")
        for k, v in item.items():
            if v and k in ["id", "title", "createDate", "bulletinType", "areaName", "content"]:
                val = str(v)[:100]
                print(f"  {k}: {val}")
        print()