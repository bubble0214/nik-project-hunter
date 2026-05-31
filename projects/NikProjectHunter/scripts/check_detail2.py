with open('/app/debug/jincaiwang/000154254477_detail.html', 'r', encoding='utf-8') as f:
    content = f.read()
# Find the middle section around id="title"
idx = content.find('id="title"')
if idx >= 0:
    print('=== Around id="title" ===')
    print(content[max(0,idx-500):idx+1000])
else:
    print('id="title" not found as attribute')
    # Check if title is in h5
    idx2 = content.find('<h5')
    print('=== Around first h5 ===')
    print(content[max(0,idx2-200):idx2+500])
    
    idx3 = content.find('detail-new')
    print('=== Around detail-new ===')
    print(content[max(0,idx3-500):idx3+500])