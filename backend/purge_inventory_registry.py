"""A7: purge inventory entry from registry.json and delete its .joblib files."""
import json, pathlib

registry_path = pathlib.Path("data/models/registry.json")
data = json.loads(registry_path.read_text())

inv_entries = data.pop("inventory", [])
print(f"Removed inventory from registry ({len(inv_entries)} version(s))")

models_dir = pathlib.Path("data/models")
deleted = []

# inv_entries is a list of version dicts
entries = inv_entries if isinstance(inv_entries, list) else list(inv_entries.values())
for meta in entries:
    if isinstance(meta, dict):
        stored = meta.get("model_path", "")
        if stored:
            p = pathlib.Path(stored)
            if not p.is_absolute():
                p = models_dir / p.name
            if p.exists():
                p.unlink()
                deleted.append(str(p))

# Glob any remaining inventory_*.joblib
for f in models_dir.glob("inventory_*.joblib"):
    f.unlink()
    deleted.append(str(f))

print(f"Deleted: {deleted or 'none found'}")
registry_path.write_text(json.dumps(data, indent=2))
print(f"Registry updated. Remaining agents: {list(data.keys())}")
