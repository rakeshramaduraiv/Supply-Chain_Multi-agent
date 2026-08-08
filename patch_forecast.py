import re

path = r"c:\Users\balan\OneDrive\Desktop\supply-chain\frontend\src\pages\ForecastPage.jsx"
with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

# 1. Fix forecastPeriod span — null-coalesce to em-dash
src = src.replace(
    '{forecastPeriod}</span>',
    "{forecastPeriod ?? '\u2014'}</span>",
    1
)

# 2. Fix cycleMonth default — remove hardcoded '2018-02'
src = src.replace(
    "useState(() => readLS('amasci_cycle_month', '2018-02'))",
    "useState(() => readLS('amasci_cycle_month', null))",
    1
)

# 3. Fix cycleTrainedUntil default — remove hardcoded '2018-01'
src = src.replace(
    "useState(() => readLS('amasci_cycle_trained_until', '2018-01'))",
    "useState(() => readLS('amasci_cycle_trained_until', null))",
    1
)

# 4. Fix backend restart reset — remove hardcoded date literals
src = src.replace(
    "_setCycleMonth('2018-02')",
    "_setCycleMonth(null)",
    1
)
src = src.replace(
    "_setCycleTrainedUntil('2018-01')",
    "_setCycleTrainedUntil(null)",
    1
)

# 5. Wire setActiveCycleIdPersisted after upload succeeds in handleIngestSyntheticMonth
# The upload result is set via setCycleUploadResult(result) — we add the cycle id setter after it
# The new CycleResponse has upload_id; we use that as the cycle anchor for resync
# Actually cycle_id comes from the WS stream; for the legacy local path we just clear it
# so the tracker shows nothing (correct — no real cycle ran)
src = src.replace(
    "setCycleUploadResult(result)\n      setCycleActualsUploaded(true)",
    "setCycleUploadResult(result)\n      setActiveCycleIdPersisted(null)  // local parse path — no real cycle\n      setCycleActualsUploaded(true)",
    1
)

# 6. Wire setActiveCycleIdPersisted in the business upload path
# The business upload (uploadBusinessActual) returns CycleResponse with upload_id
# We need to capture cycle_id from the WS stream — it arrives as the first RUNNING event
# The hook already handles this via SET_CYCLE when cycleId prop changes
# For the mutation that calls api.uploadBusinessActual, set activeCycleId from response
# Find the mutation onSuccess that sets cycleUploadResult from business upload
# The ForecastPage uses handleIngestSyntheticMonth for local CSV parse — no business API call
# The business upload is wired in business/__init__.py, not here
# So we just need to ensure that when the WS stream receives a cycle.stage event,
# useCycleStream auto-captures the cycleId (it does via SET_CYCLE in STAGE_EVENT reducer)
# No additional change needed here.

with open(path, 'w', encoding='utf-8') as f:
    f.write(src)

print("Patch applied OK")
