#!/usr/bin/env python3
import re

file_path = r'E:\code.projects\fba\FBA-Bench-Enterprise\scripts\run_competition_benchmark.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and fix the _strip_md_fences function
output = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Look for the start of _strip_md_fences function
    if 'def _strip_md_fences' in line:
        # Add the function definition
        output.append(line)
        i += 1
        
        # Skip to the opening of the function body (after docstring)
        while i < len(lines) and '"""' not in lines[i]:
            output.append(lines[i])
            i += 1
        
        # Add docstring closing
        output.append(lines[i])  # closing """
        i += 1
        
        # Now replace the function body
        output.append('    import re\n')
        output.append('    s = text.strip()\n')
        output.append('    s = re.sub(r"^```[^\\n]*\\n", "", s)\n')
        output.append('    s = re.sub(r"\\n```$", "", s)\n')
        output.append('    return s.strip()\n')
        
        # Skip the old function body until we reach the next function or end
        while i < len(lines) and not (lines[i].strip().startswith('def ') and not lines[i].startswith('    ')):
            i += 1
        
        # Add blank line before next function
        if i < len(lines):
            output.append('\n')
    else:
        output.append(line)
        i += 1

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(output)

print('✓ Fixed _strip_md_fences function')
