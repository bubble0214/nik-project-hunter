with open('/app/debug/jincaiwang/235820679562_detail.html', 'r', encoding='utf-8') as f:
    content = f.read()
print('Length:', len(content))
# Show key parts
print('=== First 2000 chars ===')
print(content[:2000])
print('=== Around id=title ===')
idx = content.find('id="title"')
if idx >= 0:
    print(content[max(0,idx-100):idx+200])
else:
    print('id="title" NOT FOUND')
print('=== Login check ===')
print('登录:', '登录' in content or 'login' in content.lower())