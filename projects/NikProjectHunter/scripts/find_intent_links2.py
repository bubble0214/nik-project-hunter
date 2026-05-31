"""Find intent links on China ZFCG"""
import httpx

r = httpx.get("http://www.ccgp.gov.cn/", timeout=10)
html = r.text

# Search for 政府采购意向公开查询
idx = html.find("政府采购意向公开查询")
if idx >= 0:
    print("Found at", idx)
    print(html[max(0,idx-200):idx+50])
    
idx2 = html.find("政府采购意向")
if idx2 >= 0:
    print("\n\nFound '政府采购意向' at", idx2)
    print(html[max(0,idx2-200):idx2+50])