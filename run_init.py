import asyncio, sys, logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
sys.path.insert(0, "/app")
from app.initialization.service import InitializationService
from pathlib import Path

async def run():
    svc = InitializationService()
    result = await svc.execute(Path("data/raw/DataCoSupplyChainDataset.csv"))
    print("STATUS:", result["status"])
    if result.get("error"):
        print("ERROR:", result["error"])
    for k, v in result.get("steps", {}).items():
        print(f"  {k}: {v.get('status','?')}")

asyncio.run(run())
