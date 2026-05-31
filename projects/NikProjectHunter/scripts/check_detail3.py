with open('/app/debug/jincaiwang/000154254477_detail.html', 'r', encoding='utf-8') as f:
    content = f.read()
# Find detail-new
idx = content.find('detail-new')
if idx >= 0:
    print('=== Around detail-new ===')
    print(content[max(0,idx-200):idx+1500])
else:
    print('detail-new not found')