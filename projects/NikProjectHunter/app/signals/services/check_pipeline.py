"""Check signal_pipeline.py for issues"""
filepath = r"C:\Users\14091\.openclaw\workspace\projects\NikProjectHunter\app\signals\services\signal_pipeline.py"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Check for duplicate lines
for i, line in enumerate(lines):
    stripped = line.strip()
    if not stripped:
        continue
    # Check if the same line appears again nearby
    for j in range(i+1, min(i+3, len(lines))):
        if lines[j].strip() == stripped and stripped not in ['', '...']:
            print(f"Possible duplicate: Line {i} and {j}: {repr(stripped)}")

# Check for company_name get with default
for i, line in enumerate(lines):
    if 'company_name' in line and 'get(' in line and 'default' in line:
        print(f"Line {i}: {repr(line)}")