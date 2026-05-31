import re
# Check the latest detail page
import glob, os
files = sorted([f for f in os.listdir('/app/debug/jincaiwang') if 'detail' in f and f.endswith('.html')])
if files:
    latest = files[-1]
    print('Latest:', latest)
    with open(f'/app/debug/jincaiwang/{latest}', 'r', encoding='utf-8') as f:
        content = f.read()
    print('Length:', len(content))
    # Check h5#title
    idx = content.find('id="title"')
    if idx >= 0:
        # Extract text around h5
        start = max(0, idx - 50)
        end = min(len(content), idx + 300)
        snippet = content[start:end]
        # Get the h5 inner text
        h5_match = re.search(r'<h5[^>]*id="title"[^>]*>(.*?)</h5>', content, re.DOTALL)
        if h5_match:
            title_text = re.sub(r'<[^>]+>', '', h5_match.group(1)).strip()
            print('TITLE:', title_text[:100])
        else:
            print('h5 with id=title found but pattern mismatch')
            print(snippet[:500])
    else:
        print('No id="title" found')
        # Check what h5 exists
        h5_all = re.findall(r'<h5[^>]*>(.*?)</h5>', content, re.DOTALL)
        print(f'h5 count: {len(h5_all)}')
        for h5 in h5_all[:3]:
            text = re.sub(r'<[^>]+>', '', h5).strip()
            print(f'  h5 text: {text[:80]}')
else:
    print('No detail files found')