"""
Set active model to the latest version_id that has a file on disk.
"""
import json
from pathlib import Path

registry_path = Path("/app/data/models/registry.json")
d = json.load(open(registry_path))

for intel_type, versions in d.items():
    # Deactivate all
    for v in versions:
        v["is_active"] = False

    # Find latest version whose file exists on disk
    best = None
    for v in reversed(versions):
        p = Path(v["model_path"])
        if p.exists():
            best = v
            break

    if best:
        best["is_active"] = True
        print(f"  {intel_type}: active -> {best['version_id']} ({best['model_path']})")
    else:
        print(f"  {intel_type}: WARNING no file found on disk for any version")

json.dump(d, open(registry_path, "w"), indent=2)
print("Done.")
