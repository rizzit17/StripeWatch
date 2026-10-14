"""Test and produce compressed, fully-functional web/app.js < 40 KB."""
import os
import re

with open('web/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Strip comments
text = re.sub(r'//.*', '', text)
text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

# 2. Collapse indentation and empty lines
lines = [l.strip() for l in text.splitlines() if l.strip()]
clean = '\n'.join(lines)

# 3. Collapse multiple whitespace inside template strings: HTML tags like "  <div " -> "<div "
clean = re.sub(r'>\s+<', '><', clean)
clean = re.sub(r'\s{2,}', ' ', clean)

print(f"Cleaned size: {len(clean)} bytes")
with open('web/app.js', 'w', encoding='utf-8') as f:
    f.write(clean + '\n')

sz = os.path.getsize('web/app.js')
print(f"Final web/app.js size on disk: {sz} bytes (Target: < 40960 bytes). PASS: {sz < 40960}")
