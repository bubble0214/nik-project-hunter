"""Fix duplicate 'summary' key in enterprise_profile.py"""
filepath = r"C:\Users\14091\.openclaw\workspace\projects\NikProjectHunter\app\signals\services\enterprise_profile.py"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if '"summary":' in line:
        print(f'Line {i}: {repr(line)}')

# Find duplicate summary keys
summary_lines = [i for i, line in enumerate(lines) if '"summary":' in line]
print(f"\nSummary key lines: {summary_lines}")

# If there are two consecutive summary lines, remove the second
if len(summary_lines) >= 2:
    # Check if they're close together
    if summary_lines[1] - summary_lines[0] <= 3:
        idx_to_remove = summary_lines[1]
        print(f"Removing duplicate summary at line {idx_to_remove}")
        del lines[idx_to_remove]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print("Fixed!")
    else:
        print("Summary lines not consecutive, might be intentional")