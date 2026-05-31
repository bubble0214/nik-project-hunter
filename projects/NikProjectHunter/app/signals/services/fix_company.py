"""Fix broken line in enterprise_profile.py"""
filepath = r"C:\Users\14091\.openclaw\workspace\projects\NikProjectHunter\app\signals\services\enterprise_profile.py"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line 192 is "if company\n" without colon
# Remove it
del lines[192]  # 0-indexed

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed: removed broken 'if company' line")
print(f"Total lines: {len(lines)}")