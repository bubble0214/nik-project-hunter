"""Fix signal_pipeline.py"""
filepath = r"C:\Users\14091\.openclaw\workspace\projects\NikProjectHunter\app\signals\services\signal_pipeline.py"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix duplicate "stored = []" at lines 162-163
# Fix duplicate "analysis" key in analyzed dict
# Fix the _update_enterprise_profiles method

# Check specific lines
print(f"Line 162: {repr(lines[162])}")
print(f"Line 163: {repr(lines[163])}")

# Fix duplicate stored
if lines[162].strip() == 'stored = []' and lines[163].strip() == 'stored = []':
    del lines[163]
    print("Fixed duplicate stored = []")

# Fix the analyzed dict - look for duplicate "analysis": analysis,
fixed_content = ''.join(lines)

# Find the problematic section
# The issue is: 
#     analyzed.append({
#         "signal_type": signal.signal_type,
#         "company_name": signal.company_name,
#         "id": signal.id,
#         "analysis": analysis,
#         **signal_data,
#         "analysis": analysis,
#     })

old = '        "analysis": analysis,\n        **signal_data,\n        "analysis": analysis,'
new = '        "analysis": analysis,\n        **signal_data,'
if old in fixed_content:
    fixed_content = fixed_content.replace(old, new)
    print("Fixed duplicate analysis key in dict")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print("Pipeline fixes applied")