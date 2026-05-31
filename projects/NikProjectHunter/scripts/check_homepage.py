import re
with open('/app/debug/jincaiwang/000646990407_home_page.html', 'r', encoding='utf-8') as f:
    content = f.read()
print('Length:', len(content))
print('cgNoticeList:', 'cgNoticeList' in content)
print('zjNoticeList:', 'zjNoticeList' in content)
print('jgNoticeList:', 'jgNoticeList' in content)
print('gzNoticeList:', 'gzNoticeList' in content)
ids = re.findall(r'id="([^"]+)"', content)
print('IDs found:', ids[:30])
print('Has h5:', 'h5' in content or '<h5' in content)