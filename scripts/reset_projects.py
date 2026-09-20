"""Reset masivo de proyectos para reprocesar el pipeline desde cero.

Borra la huella de generacion de propuestas de los proyectos que NO fueron
enviados a Workana, para que el bot los vuelva a tomar como nuevos.

Alcance:
  - Estados objetivo: ``proposal_generated`` y ``analyzed``.
  - Por cada proyecto objetivo:
      * ``proposal_status`` -> ``analyzed``
      * borrar ``full_description`` (el bot exige que falte para procesarlo)
      * borrar sus documentos en ``proposal_versions``,
        ``requirement_analyses`` y ``technical_estimates``
  - NUNCA toca ``submited_to_workana`` (ni estado ni versiones).

Uso (SIEMPRE dry-run primero):
    docker exec workana_bot python /usr/src/reset_projects.py            # dry-run
    docker exec workana_bot python /usr/src/reset_projects.py --apply    # ejecuta

Dry-run es el modo por defecto: imprime que haria sin modificar nada. Solo
``--apply`` realiza cambios.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

TARGET_STATUSES = ["proposal_generated", "analyzed"]
DERIVED_COLLECTIONS = [
    "proposal_versions",
    "requirement_analyses",
    "technical_estimates",
]


async def main() -> None:
    apply_changes = "--apply" in sys.argv

    mongo_uri = os.getenv("MONGO_URI")
    db_name = os.getenv("MONGO_DB_NAME", "workana_bot")
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]
    projects = db["projects"]

    host = mongo_uri.split("@")[-1].split("/")[0] if mongo_uri else "?"
    mode = "APPLY (modificara datos)" if apply_changes else "DRY-RUN (solo muestra)"
    print(f"=== Reset de proyectos ===")
    print(f"  Atlas : {host} / db={db_name}")
    print(f"  Modo  : {mode}")
    print(f"  Estados objetivo: {TARGET_STATUSES}")
    print(f"  NO se toca      : submited_to_workana")
    print()

    # 1) Recolectar los proyectos objetivo (con su link_hash)
    targets = []
    async for doc in projects.find(
        {"proposal_status": {"$in": TARGET_STATUSES}},
        {"link_hash": 1, "proposal_status": 1, "title": 1},
    ):
        targets.append(doc)

    print(f"Proyectos objetivo: {len(targets)}")

    # Resumen por estado
    by_status: dict[str, int] = {}
    for t in targets:
        s = t.get("proposal_status", "?")
        by_status[s] = by_status.get(s, 0) + 1
    for s, n in sorted(by_status.items()):
        print(f"    {s}: {n}")
    print()

    # 2) Contar huella a borrar en colecciones derivadas
    target_hashes = [t["link_hash"] for t in targets if t.get("link_hash")]
    print("Documentos derivados a borrar:")
    derived_counts = {}
    for col in DERIVED_COLLECTIONS:
        n = await db[col].count_documents({"link_hash": {"$in": target_hashes}})
        derived_counts[col] = n
        print(f"    {col}: {n}")
    print()

    # 3) Proyectos que quedan intactos (sanity)
    sub_count = await projects.count_documents({"proposal_status": "submited_to_workana"})
    print(f"Proyectos intactos (submited_to_workana): {sub_count}")
    print()

    if not apply_changes:
        print("DRY-RUN: no se modifico nada. Re-ejecutar con --apply para aplicar.")
        client.close()
        return

    # 4) Aplicar cambios
    print("Aplicando cambios...")
    result = await projects.update_many(
        {"proposal_status": {"$in": TARGET_STATUSES}},
        {
            "$set": {"proposal_status": "analyzed"},
            "$unset": {"full_description": "", "proposal_at": ""},
        },
    )
    print(f"  projects actualizados: {result.modified_count}")

    for col in DERIVED_COLLECTIONS:
        res = await db[col].delete_many({"link_hash": {"$in": target_hashes}})
        print(f"  {col} borrados: {res.deleted_count}")

    print()
    print("=== Resumen final ===")
    agg: dict[str, int] = {}
    async for d in projects.find({}, {"proposal_status": 1}):
        s = d.get("proposal_status", "(sin status)")
        agg[s] = agg.get(s, 0) + 1
    for s, n in sorted(agg.items(), key=lambda x: -x[1]):
        print(f"    {s}: {n}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
