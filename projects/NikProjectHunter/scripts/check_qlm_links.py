import re
with open('/app/debug/beijing_ggzy/012721408570_list_page.html', 'r', encoding='utf-8') as f:
    content = f.read()
# Find all a[href] that look like project links
links = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', content)
# Show links that look like project/detail pages
print(f'Total links: {len(links)}')
for href, text in links:
    text = re.sub(r'<[^>]+>', '', text).strip()
    if len(text) > 5 and ('bid' in href or 'zbgg' in href or 'detail' in href or 'notice' in href or 'info' in href):
        print(f'  {href[:80]} -> [{text[:60]}]')
    elif len(text) > 10:
        print(f'  {href[:80]} -> [{text[:60]}]')