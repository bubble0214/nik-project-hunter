import sys
path = sys.argv[1]
with open(path, 'r', errors='ignore') as f:
    content = f.read()
# Extract visible text between tags
import re
text = re.sub(r'<[^>]+>', ' ', content)
text = re.sub(r'\s+', ' ', text).strip()
print(text[:2000])