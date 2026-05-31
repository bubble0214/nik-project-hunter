"""Fix the duplicate impact_level in signal_analyzer.py"""
filepath = r"C:\Users\14091\.openclaw\workspace\projects\NikProjectHunter\app\signals\services\__init__.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

old = (
    '              \'  "impact_level": "low/medium/high",\\n\'\n'
    '              \'  "impact_level": "low/medium/high",\\n\'\n'
    '              \'  "recommended_strategy": "建议应对策略",\\n\'\n'
)

new = (
    '              \'  "impact_level": "low/medium/high",\\n\'\n'
    '              \'  "recommended_strategy": "建议应对策略",\\n\'\n'
)

if old in content:
    content = content.replace(old, new)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed: removed duplicate impact_level")
else:
    print("Pattern not found, checking for alternatives...")
    # Check what's actually around that area
    idx = content.find('"impact_level": "low/medium/high"')
    if idx >= 0:
        # Show context
        start = max(0, idx - 100)
        end = min(len(content), idx + 200)
        print(repr(content[start:end]))
    else:
        print("impact_level pattern not found at all")