"""Diagnostico del estado de un lote de procesamiento (sin leer logs).

Resume, de forma compacta: cuantos proyectos hay por estado, cuantos documentos
se han generado, y una tabla con los ultimos proyectos procesados (con su
estimacion) para evaluar calidad rapidamente.

Uso:
    docker exec workana_bot python /usr/src/diag_lote.py
    docker exec workana_bot python /usr/src/diag_lote.py --limit 30
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()


async def main() -> None:
    limit = 30
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    db = AsyncIOMotorClient(os.getenv("MONGO_URI"))[
        os.getenv("MONGO_DB_NAME", "workana_bot")
    ]

    print("=" * 70)
    print("DIAGNOSTICO DE LOTE")
    print("=" * 70)

    # 1) Proyectos por estado
    print("\n--- Proyectos por proposal_status ---")
    agg: dict[str, int] = {}
    async for d in db.projects.find({}, {"proposal_status": 1}):
        s = d.get("proposal_status", "(sin status)")
        agg[s] = agg.get(s, 0) + 1
    for s, n in sorted(agg.items(), key=lambda x: -x[1]):
        print(f"  {s:24} {n:4}")
    print(f"  {'TOTAL':24} {await db.projects.count_documents({}):4}")

    # 2) Colecciones derivadas
    print("\n--- Documentos generados ---")
    for c in ["requirement_analyses", "technical_estimates", "proposal_versions"]:
        print(f"  {c:24} {await db[c].count_documents({}):4}")

    # 3) Semáforo
    sem = await db.process_semaphore.find_one({})
    print(f"\n  semaforo bloqueado: {sem.get('is_locked') if sem else '?'}")

    # 4) Ultimos proyectos procesados (con su estimacion)
    print(f"\n--- Ultimos {limit} proyectos procesados (proposal_generated) ---")
    print(f"  {'status':10} {'tipo':10} {'hrs':>6} {'USD':>8}  title")
    count = 0
    async for p in db.projects.find(
        {"proposal_status": "proposal_generated"},
        {"link_hash": 1, "title": 1},
    ).sort("proposal_at", -1).limit(limit):
        h = p["link_hash"]
        te = await db.technical_estimates.find_one(
            {"link_hash": h}, sort=[("created_at", -1)]
        )
        et = te.get("estimate_type", "?") if te else "(sin est)"
        hrs = te.get("summary", {}).get("total_hours", "?") if te else "?"
        usd = te.get("summary", {}).get("total_budget", "?") if te else "?"
        title = (p.get("title") or "")[:42]
        print(f"  {'gen':10} {et:10} {str(hrs):>6} {str(usd):>8}  {title}")
        count += 1
    if count == 0:
        print("  (ninguno)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
