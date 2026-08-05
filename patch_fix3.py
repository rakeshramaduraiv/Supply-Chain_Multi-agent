# -*- coding: utf-8 -*-
path = 'frontend/src/pages/ForecastPage.jsx'
with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

# Find the setUploadHistory block by unique anchor
anchor = "setUploadHistory(prev => [{"
idx = src.find(anchor)

result = 'anchor not found'
if idx >= 0:
    # Find the closing of this call: }, ...prev])
    close = src.find("}, ...prev])", idx)
    if close >= 0:
        old_block = src[idx : close + len("}, ...prev])")]
        # Build replacement preserving indentation
        indent = ""
        line_start = src.rfind('\n', 0, idx) + 1
        for ch in src[line_start:idx]:
            if ch in (' ', '\t'):
                indent += ch
            else:
                break
        inner = old_block[len(anchor):-(len("}, ...prev])"))]  # content between [{ and }, ...prev])
        new_block = (
            "setUploadHistory(prev => {\n" +
            indent + "  const next = [{" + inner + "}, ...prev]\n" +
            indent + "  writeLS('amasci_upload_history', next)\n" +
            indent + "  return next\n" +
            indent + "})"
        )
        src = src[:idx] + new_block + src[idx + len(old_block):]
        with open(path, 'w', encoding='utf-8') as f:
            f.write(src)
        result = 'PATCHED'
    else:
        result = 'close not found'

with open('_p.txt', 'w', encoding='utf-8') as o:
    o.write(result + '\n')
