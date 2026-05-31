import os, re
files = sorted([f for f in os.listdir('/app/debug/jincaiwang') if 'detail' in f and f.endswith('.html')], key=lambda f: os.path.getmtime('/app/debug/jincaiwang/' + f))
# Get the 5 most recent files
for f in files[-5:]:
    mtime = os.path.getmtime('/app/debug/jincaiwang/' + f)
    size = os.path.getsize('/app/debug/jincaiwang/' + f)
    with open('/app/debug/jincaiwang/' + f, 'r', encoding='utf-8') as fh:
        content = fh.read()
    h5_match = re.search(r'<h5[^>]*id="title"[^>]*>(.*?)</h5>', content, re.DOTALL)
    title = ''
    if h5_match:
        title = re.sub(r'<[^>]+>', '', h5_match.group(1)).strip()[:80]
    print(f'{f}: {size}B, title=[{title}]')