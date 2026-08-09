import json
from pathlib import Path

path = "/app/data/models/registry.json"
d = json.load(open(path))
for intel_type, versions in d.items():
    for v in versions:
        v["is_active"] = False
    for v in reversed(versions):
        p = Path(v["model_path"].replace("\\", "/"))
        if not p.is_absolute():
            p = Path("/app") / p
        if p.exists():
            v["model_path"] = str(p)
            v["is_active"] = True
            print(f"  {intel_type} -> {v['version_id']}")
            break
    else:
        print(f"  {intel_type}: WARNING no file found on disk")
json.dump(d, open(path, "w"), indent=2)
print("Done.")
