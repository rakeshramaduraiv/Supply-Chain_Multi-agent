path = 'backend/app/api/v1/endpoints/health.py'
with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

old1 = 'import logging\n\nfrom fastapi import APIRouter, status'
new1 = 'import logging\nimport uuid\n\nfrom fastapi import APIRouter, status\n\n# Generated once per process — changes every time the backend restarts\n_SESSION_ID = str(uuid.uuid4())'

old2 = '@router.get(\n    "/live",\n    status_code=status.HTTP_200_OK,\n    summary="Liveness Probe",\n)\nasync def liveness() -> dict:\n    """Kubernetes liveness probe."""\n    return {"status": "alive"}'
new2 = '@router.get(\n    "/live",\n    status_code=status.HTTP_200_OK,\n    summary="Liveness Probe",\n)\nasync def liveness() -> dict:\n    """Kubernetes liveness probe."""\n    return {"status": "alive", "session_id": _SESSION_ID}'

assert old1 in src, "PATCH1 not found"
assert old2 in src, "PATCH2 not found"

src = src.replace(old1, new1)
src = src.replace(old2, new2)

with open(path, 'w', encoding='utf-8') as f:
    f.write(src)

with open('_p.txt', 'w') as o:
    o.write('DONE\n')
