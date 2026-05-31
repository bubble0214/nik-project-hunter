"""Test Shandong ZFCG API"""
import httpx, json

r = httpx.post(
    'http://www.ccgp-shandong.gov.cn:8087/api/website/site/getListByCode',
    json={'colCode':'0301','area':'370000','currentPage':1,'pageSize':12,'homePage':1,'mergeType':0,'cityType':1},
    timeout=15
)
data = r.json()
print('Status:', r.status_code)
print('Success:', data.get('success'))
items = data.get('data', {}).get('data', [])
print('Items:', len(items))
if items:
    first = items[0]
    print('\nFirst item:')
    for k, v in first.items():
        if v:
            print(f'  {k}: {str(v)[:100]}')
    print('\nFirst 10 titles:')
    for item in items[:10]:
        print(f'  {item.get("title","")[:60]:60s} | {item.get("createDate","")} | id={item.get("id","")}')