import asyncio, sys, os, json
sys.path.insert(0, '/app')
os.environ['ALLOW_ENRICHMENT_FALLBACK'] = 'false'

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s', stream=sys.stderr)

from app.initialization.service import InitializationService

# Delete .initialized sentinel to force re-run
from pathlib import Path
from app.core.config import get_settings
settings = get_settings()
sentinel = Path(settings.model_dir) / '.initialized'
if sentinel.exists():
    sentinel.unlink()
    print('Deleted .initialized sentinel', file=sys.stderr, flush=True)

result = asyncio.run(InitializationService().execute())

print(json.dumps({
    'status': result.get('status'),
    'error': result.get('error', ''),
    'steps': {k: {'status': v.get('status'), 'ms': round(v.get('duration_ms', 0))} for k, v in result.get('steps', {}).items()}
}, indent=2))
sys.stdout.flush()
