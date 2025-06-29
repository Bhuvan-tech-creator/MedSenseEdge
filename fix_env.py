#!/usr/bin/env python3
"""
Fix .env file formatting
"""

import re

# Read the .env file
with open('.env', 'r') as f:
    content = f.read()

# Fix the formatting
# Remove spaces around = and remove quotes
fixed_content = re.sub(r'(\w+)\s*=\s*"([^"]+)"', r'\1=\2', content)
fixed_content = re.sub(r'(\w+)\s*=\s*\'([^\']+)\'', r'\1=\2', fixed_content)
fixed_content = re.sub(r'(\w+)\s*=\s*([^\n]+)', lambda m: f"{m.group(1)}={m.group(2).strip()}", fixed_content)

# Write back
with open('.env', 'w') as f:
    f.write(fixed_content)

print("✅ Fixed .env file formatting")
print("\nUpdated entries:")
for line in fixed_content.strip().split('\n'):
    if '=' in line:
        key = line.split('=')[0]
        value = line.split('=', 1)[1]
        if len(value) > 20:
            print(f"  {key}={value[:20]}...")
        else:
            print(f"  {line}") 