# -*- coding: utf-8 -*-
path = 'frontend/src/pages/ForecastPage.jsx'
with open(path, 'rb') as f:
    raw = f.read()

src = raw.decode('utf-8').replace('\r\n', '\n')

# Use a tighter anchor — just the useState line with its inline comment
anchor = "  const [stepLogs, setStepLogs] = useState({}) // { [stepNum]: { lines: string[], done: bool } }"

reset_effect = """  // ── Backend restart detection: if session_id changes, backend restarted → reset lifecycle
  useEffect(() => {
    api.live().then(r => {
      const sid = r?.data?.session_id
      if (!sid) return
      const stored = localStorage.getItem('amasci_backend_session')
      if (stored && stored !== sid) {
        const keys = [
          'amasci_cycle_step', 'amasci_cycle_month', 'amasci_cycle_trained_until',
          'amasci_cycle_actuals_uploaded', 'amasci_cycle_model_retrained',
          'amasci_cycle_upload_result', 'amasci_completed_cycles',
          'amasci_upload_history', 'amasci_rca_focus', 'amasci_graph_focus',
          'amasci_forecast_incidents',
        ]
        keys.forEach(k => localStorage.removeItem(k))
        _setCycleStep(1)
        _setCycleMonth('2018-02')
        _setCycleTrainedUntil('2018-01')
        _setCycleActualsUploaded(false)
        _setCycleModelRetrained(false)
        _setCycleUploadResult(null)
        _setCompletedCycles([])
        setUploadHistory([])
        setStepLogs({})
        toast.info('Backend restarted \u2014 lifecycle reset to 2018-02 Step 1')
      }
      localStorage.setItem('amasci_backend_session', sid)
    }).catch(() => {})
  }, [])

"""

found = anchor in src
with open('_p.txt', 'w') as o:
    o.write('anchor found: ' + str(found) + '\n')

if found:
    src = src.replace(anchor, reset_effect + anchor)
    out = src.replace('\n', '\r\n')
    with open(path, 'wb') as f:
        f.write(out.encode('utf-8'))
    with open('_p.txt', 'a') as o:
        o.write('DONE\n')
else:
    idx = src.find('stepLogs, setStepLogs')
    with open('_p.txt', 'a') as o:
        o.write('stepLogs idx: ' + str(idx) + '\n')
        if idx >= 0:
            o.write(repr(src[idx-4:idx+120]) + '\n')
