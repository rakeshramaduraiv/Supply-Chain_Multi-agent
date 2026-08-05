import re

path = 'frontend/src/pages/ForecastPage.jsx'
with open(path, 'rb') as f:
    raw = f.read()

src = raw.decode('utf-8')

changes = 0

# Fix 1: UploadZone onFile — pass file to handleIngestSyntheticMonth
if 'handleIngestSyntheticMonth(cycleMonth)' in src:
    src = src.replace(
        'handleIngestSyntheticMonth(cycleMonth)',
        'handleIngestSyntheticMonth(cycleMonth, file)',
        1  # only the onFile call site (first occurrence in the upload zone)
    )
    changes += 1
    open('_p.txt','a').write('fix1 applied\n')
else:
    open('_p.txt','a').write('fix1 NOT FOUND\n')

# Fix 2: Persist uploadHistory to localStorage — change useState init
old2 = 'const [uploadHistory, setUploadHistory] = useState([])'
new2 = "const [uploadHistory, setUploadHistory] = useState(() => readLS('amasci_upload_history', []))"
if old2 in src:
    src = src.replace(old2, new2)
    changes += 1
    open('_p.txt','a').write('fix2 applied\n')
else:
    open('_p.txt','a').write('fix2 NOT FOUND\n')

# Fix 3: persist uploadHistory writes — wrap setUploadHistory to also call writeLS
# Find the setUploadHistory call and replace it
old3 = "setUploadHistory(prev => [{"
if old3 in src:
    # Find the full block
    idx = src.find(old3)
    # Find the closing }]) of this call
    end = src.find("}])", idx)
    if end > 0:
        old_block = src[idx:end+3]
        # Extract the object literal between [{ and }]
        inner_start = old_block.find('[{') + 1
        inner_end = old_block.rfind('}]') + 2
        inner = old_block[inner_start:inner_end]
        new_block = (
            "setUploadHistory(prev => {\n"
            "        const next = [" + inner.strip() + ", ...prev]\n"
            "        writeLS('amasci_upload_history', next)\n"
            "        return next\n"
            "      })"
        )
        src = src[:idx] + new_block + src[idx+len(old_block):]
        changes += 1
        open('_p.txt','a').write('fix3 applied\n')
    else:
        open('_p.txt','a').write('fix3 end not found\n')
else:
    open('_p.txt','a').write('fix3 NOT FOUND\n')

open('_p.txt','a').write(f'total changes: {changes}\n')

with open(path, 'w', encoding='utf-8') as f:
    f.write(src)

open('_p.txt','a').write('DONE\n')
