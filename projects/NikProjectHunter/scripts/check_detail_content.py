import os, re
files = sorted([f for f in os.listdir('/app/debug/jincaiwang') if 'detail' in f and f.endswith('.html')], key=lambda f: os.path.getmtime('/app/debug/jincaiwang/' + f))
for f in files[-5:]:
    size = os.path.getsize('/app/debug/jincaiwang/' + f)
    with open('/app/debug/jincaiwang/' + f, 'r', encoding='utf-8') as fh:
        content = fh.read()
    # Extract detail-new content
    dn_match = re.search(r'<div[^>]*id="detail-new"[^>]*>(.*?)</div>\s*<div[^>]*id="clearfix"', content, re.DOTALL)
    dn_text = ''
    if dn_match:
        dn_text = re.sub(r'<[^>]+>', '', dn_match.group(1)).strip()[:100]
    print(f'{f}: {size}B, detail-new=[{dn_text}]')