import os, re
files = sorted([f for f in os.listdir('/app/debug/jincaiwang') if 'detail' in f and f.endswith('.html')], key=lambda f: os.path.getmtime('/app/debug/jincaiwang/' + f))
latest = files[-1]
print('Latest:', latest)
size = os.path.getsize('/app/debug/jincaiwang/' + latest)
print('Size:', size)
with open('/app/debug/jincaiwang/' + latest, 'r', encoding='utf-8') as f:
    content = f.read()
# Check h5#title
h5_match = re.search(r'<h5[^>]*id="title"[^>]*>(.*?)</h5>', content, re.DOTALL)
if h5_match:
    inner = re.sub(r'<[^>]+>', '', h5_match.group(1)).strip()
    print(f'Title: [{inner[:100]}]')
else:
    print('h5#title not found')
# Check detail-new
if 'detail-new' in content:
    dn_idx = content.find('detail-new')
    after_dn = content[dn_idx:dn_idx+200]
    print(f'detail-new found, text after: {after_dn[:100]}')
else:
    print('detail-new NOT found')