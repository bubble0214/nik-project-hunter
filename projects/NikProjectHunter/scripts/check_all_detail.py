import os, re, glob
# Get all files sorted by modification time
files = []
for f in os.listdir('/app/debug/jincaiwang'):
    if 'detail' in f and f.endswith('.html'):
        path = f'/app/debug/jincaiwang/{f}'
        mtime = os.path.getmtime(path)
        files.append((mtime, f))
files.sort(reverse=True)
print('Top 5 latest:')
for mtime, fname in files[:5]:
    size = os.path.getsize(f'/app/debug/jincaiwang/{fname}')
    print(f'  {fname} ({size}B)')
    # Quick check title content
    with open(f'/app/debug/jincaiwang/{fname}', 'r', encoding='utf-8') as f:
        content = f.read()
    h5_match = re.search(r'<h5[^>]*id="title"[^>]*>(.*?)</h5>', content, re.DOTALL)
    if h5_match:
        inner = re.sub(r'<[^>]+>', '', h5_match.group(1)).strip()
        print(f'    Title: [{inner[:80]}]')