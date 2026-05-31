"""Fix duplicate 'summary' key at lines 169-170"""
filepath = r"C:\Users\14091\.openclaw\workspace\projects\NikProjectHunter\app\signals\services\enterprise_profile.py"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove line 170 (the second "summary": "画像构建失败" line)
print(f"Line 170: {repr(lines[170])}")
del lines[170]

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed: removed duplicate 'summary' key at line 170")