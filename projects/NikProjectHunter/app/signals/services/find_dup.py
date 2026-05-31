"""Fix the duplicate impact_level in policy analysis"""
filepath = r"C:\Users\14091\.openclaw\workspace\projects\NikProjectHunter\app\signals\services\__init__.py"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the policy section
for i, line in enumerate(lines):
    if 'impact_level' in line:
        print(f'Line {i}: {repr(line)}')