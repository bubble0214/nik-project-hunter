import os, re
files = sorted([f for f in os.listdir('/app/debug/jincaiwang') if 'detail' in f and f.endswith('.html')])
if files:
    latest = files[-1]
    print('Latest:', latest)
    with open(f'/app/debug/jincaiwang/{latest}', 'r', encoding='utf-8') as f:
        content = f.read()
    print('Length:', len(content))
    # Check h5#title content
    h5_match = re.search(r'<h5[^>]*id="title"[^>]*>(.*?)</h5>', content, re.DOTALL)
    if h5_match:
        inner = h5_match.group(1)
        title_text = re.sub(r'<[^>]+>', '', inner).strip()
        print(f'Title inner: [{title_text[:100]}]')
        print(f'Title length: {len(title_text)}')
    # Check detail-new
    dn_idx = content.find('id="detail-new"')
    if dn_idx >= 0:
        print('detail-new found')
    else:
        print('detail-new NOT found')
    # Check login
    print('Login link:', '登录' in content)
    # Check how many h5 have content
    h5_all = re.findall(r'<h5[^>]*>(.*?)</h5>', content, re.DOTALL)
    for i, h5 in enumerate(h5_all):
        text = re.sub(r'<[^>]+>', '', h5).strip()
        if text:
            print(f'h5[{i}]: [{text[:80]}]')