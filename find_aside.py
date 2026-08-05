import sys

path = r'c:\Users\balan\OneDrive\Desktop\supply-chain\frontend\src\pages\RiskPage.jsx'
with open(path, 'rb') as f:
    raw = f.read()

# Find the first </aside> after queueScroll
START = b'          <div className={s.queueScroll}>'
i_start = raw.find(START)
print('queueScroll at:', i_start, file=sys.stderr)

# Find </aside> after that
i_aside = raw.find(b'</aside>', i_start)
print('aside at:', i_aside, file=sys.stderr)
print(repr(raw[i_aside-20:i_aside+100]), file=sys.stderr)

# Find what comes after </aside>
print('after aside:', repr(raw[i_aside+8:i_aside+80]), file=sys.stderr)
