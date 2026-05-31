"""Fix the duplicate impact_level lines 268-269"""
filepath = r"C:\Users\14091\.openclaw\workspace\projects\NikProjectHunter\app\signals\services\__init__.py"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Lines 268-269 (0-indexed) are the duplicates
# Line 268:             '  "impact_level": "low/medium/high",\n'
# Line 269:             '  "impact_level": "low/medium/high",\n'  (it's cut off)

print(f'Line 268: {repr(lines[268])}')
print(f'Line 269: {repr(lines[269])}')
print(f'Line 270: {repr(lines[270])}')