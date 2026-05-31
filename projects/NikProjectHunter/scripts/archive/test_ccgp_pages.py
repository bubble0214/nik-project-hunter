import httpx, re
r = httpx.get('http://www.ccgp.gov.cn/cggg/zygg/gkzb/', headers={'User-Agent': 'Mozilla/5.0'}, follow_redirects=True)
print('len:', len(r.text))
links = re.findall(r'href=["\x27]([^"\x27]+)["\x27]', r.text)
# Filter for announcement links
for l in links:
    if l.startswith('./') and 't202' in l:
        print('  ' + l)
print('---')
# Check all ./ links
for l in links:
    if l.startswith('./'):
        print('  ' + l)