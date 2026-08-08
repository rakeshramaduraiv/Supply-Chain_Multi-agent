path = r"c:\Users\balan\OneDrive\Desktop\supply-chain\frontend\src\pages\ForecastPage.jsx"
with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

# 1. Replace old import with new imports
src = src.replace(
    "import ActualUploadWorkflow from '../components/domain/ActualUploadWorkflow'",
    "import CycleStageTracker from '../components/domain/CycleStageTracker'\r\nimport { useCycleStream } from '../hooks/useCycleStream'",
    1
)

# 2. Add activeCycleId state + useCycleStream after isIngestingActuals state line
old_state = "  const [isIngestingActuals, setIsIngestingActuals] = useState(false)"
new_state = (
    "  const [isIngestingActuals, setIsIngestingActuals] = useState(false)\r\n\r\n\r\n"
    "  // Active cycle id \u2014 set when upload_actual returns; drives useCycleStream\r\n\r\n\r\n"
    "  const [activeCycleId, setActiveCycleId] = useState(() => readLS('amasci_active_cycle_id', null))\r\n\r\n\r\n"
    "  const setActiveCycleIdPersisted = (v) => { setActiveCycleId(v); writeLS('amasci_active_cycle_id', v) }\r\n\r\n\r\n"
    "  const { stages: cycleStages, complete: cycleComplete } = useCycleStream(activeCycleId)"
)
src = src.replace(old_state, new_state, 1)

# 3. Replace ActualUploadWorkflow JSX with CycleStageTracker
old_jsx = (
    "          <ActualUploadWorkflow\r\n\r\n\r\n            uploadResult={cycleUploadResult}\r\n\r\n\r\n"
    "            period={cycleMonth}\r\n\r\n\r\n"
    "            isIngesting={isIngestingActuals}\r\n\r\n\r\n"
    "            onComplete={() => setIsIngestingActuals(false)}\r\n\r\n\r\n"
    "          />"
)
new_jsx = (
    "          <CycleStageTracker\r\n\r\n\r\n"
    "            stages={cycleStages}\r\n\r\n\r\n"
    "            complete={cycleComplete}\r\n\r\n\r\n"
    "            metrics={cycleUploadResult?.metrics ?? null}\r\n\r\n\r\n"
    "            period={cycleMonth || forecastPeriod || '\u2014'}\r\n\r\n\r\n"
    "          />"
)
if old_jsx in src:
    src = src.replace(old_jsx, new_jsx, 1)
    print("JSX replaced OK")
else:
    # Try with \n instead of \r\n
    old_jsx2 = old_jsx.replace('\r\n', '\n')
    if old_jsx2 in src:
        src = src.replace(old_jsx2, new_jsx.replace('\r\n', '\n'), 1)
        print("JSX replaced OK (LF)")
    else:
        print("WARNING: JSX pattern not found — doing line-based replacement")
        lines = src.split('\n')
        out = []
        i = 0
        while i < len(lines):
            if 'ActualUploadWorkflow' in lines[i] and '<ActualUploadWorkflow' in lines[i]:
                # collect until />
                while i < len(lines) and '/>' not in lines[i]:
                    i += 1
                i += 1  # skip the /> line
                out.append('          <CycleStageTracker')
                out.append('            stages={cycleStages}')
                out.append('            complete={cycleComplete}')
                out.append('            metrics={cycleUploadResult?.metrics ?? null}')
                out.append("            period={cycleMonth || forecastPeriod || '\u2014'}")
                out.append('          />')
            else:
                out.append(lines[i])
                i += 1
        src = '\n'.join(out)
        print("JSX replaced via line scan")

# 4. Fix forecastPeriod span null-coalesce
src = src.replace(
    '{forecastPeriod}</span>',
    "{forecastPeriod ?? '\u2014'}</span>",
    1
)

# 5. Remove hardcoded date defaults
src = src.replace(
    "useState(() => readLS('amasci_cycle_month', '2018-02'))",
    "useState(() => readLS('amasci_cycle_month', null))",
    1
)
src = src.replace(
    "useState(() => readLS('amasci_cycle_trained_until', '2018-01'))",
    "useState(() => readLS('amasci_cycle_trained_until', null))",
    1
)
src = src.replace("_setCycleMonth('2018-02')", "_setCycleMonth(null)", 1)
src = src.replace("_setCycleTrainedUntil('2018-01')", "_setCycleTrainedUntil(null)", 1)

# 6. Remove Inventory Agent reference (purged from backend)
src = src.replace(
    "    const agentMap = ['Logistics Agent', 'Demand Agent', 'Inventory Agent', 'Supplier Agent', 'Logistics Agent', 'Demand Agent']",
    "    const agentMap = ['Logistics Agent', 'Demand Agent', 'Supplier Agent', 'Logistics Agent', 'Demand Agent', 'Supplier Agent']",
    1
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(src)

print("All patches applied OK")
