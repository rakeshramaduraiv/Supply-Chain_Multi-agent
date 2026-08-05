src = open('frontend/src/pages/ForecastPage.jsx','rb').read().decode('utf-8')
idx = src.find('errorDiagnostics = useMemo')
chunk = src[idx:idx+600]
open('_p.txt','w').write(repr(chunk))
