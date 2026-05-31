import re
with open('/app/debug/jincaiwang/000154254477_detail.html', 'r', encoding='utf-8') as f:
    content = f.read()
# Find the detail.js script reference
# Check what JS files are loaded
scripts = re.findall(r'src="([^"]+\.js)"', content)
print('JS scripts:')
for s in scripts:
    print(f'  {s}')
# Find inline JS
inline_scripts = re.findall(r'<script[^>]*>([\s\S]*?)</script>', content)
for i, s in enumerate(inline_scripts):
    if 'noticeDetail' in s or 'ajax' in s or 'load' in s.lower():
        print(f'Inline script {i} has noticeDetail/ajax/load:')
        print(s[:500])
        print('---')