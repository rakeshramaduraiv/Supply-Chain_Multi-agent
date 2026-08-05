import sys

path = r'c:\Users\balan\OneDrive\Desktop\supply-chain\frontend\src\pages\RiskPage.jsx'
with open(path, 'rb') as f:
    raw = f.read()

lines = raw.split(b'\n')
for i, line in enumerate(lines[1325:1350], start=1326):
    print(f'{i}: {repr(line[:100])}', file=sys.stderr)
