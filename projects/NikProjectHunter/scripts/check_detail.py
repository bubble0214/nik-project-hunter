import re
with open('/app/debug/jincaiwang/000154254477_detail.html', 'r', encoding='utf-8') as f:
    content = f.read()
print('Length:', len(content))
for t in ['h1','h2','h3','h4','h5','h6']:
    count = content.count('<' + t + ' ')
    if count > 0:
        print(f'{t}: {count}')
    count2 = content.count('<' + t + '>')
    if count2 > 0:
        print(f'{t}>: {count2}')
# Check specific selectors
print('id="title":', 'id="title"' in content)
print("id='title':", "id='title'" in content)
print('detail-new:', 'detail-new' in content)
print('detail-content:', 'detail-content' in content)
print('article-content:', 'article-content' in content)
# Title classes
title_classes = re.findall(r'class="([^"]*title[^"]*)"', content)
print('Title classes:', title_classes[:10])
# Also check first 3000 chars
print('---START---')
print(content[:2000])
print('---END---')