"""Fix the duplicate impact_level lines"""
filepath = r"C:\Users\14091\.openclaw\workspace\projects\NikProjectHunter\app\signals\services\__init__.py"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove line 268 (the second duplicate), keep line 267 (the first)
# Lines: 267 is the end of budget_impact, 268 is first impact_level, 269 is duplicate
# We want to remove line 269 (the duplicate)
del lines[269]  # 0-indexed, remove the duplicate

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed: removed duplicate impact_level line")
print(f"Total lines: {len(lines)}")