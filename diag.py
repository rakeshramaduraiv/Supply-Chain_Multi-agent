import sys, re

path = r'c:\Users\balan\OneDrive\Desktop\supply-chain\frontend\src\pages\RiskPage.jsx'
with open(path, 'rb') as f:
    raw = f.read()

print('size:', len(raw), file=sys.stderr)

# Show lines 1340-1350 to understand the right panel issue
lines = raw.split(b'\n')
for i, line in enumerate(lines[1338:1355], start=1339):
    print(f'{i}: {repr(line[:80])}', file=sys.stderr)
