"""Script de prueba E2E del pipeline por etapas contra Atlas (proyecto real).

Uso:
    docker exec workana_bot python -m scripts.test_pipeline_atlas
o en el host con PYTHONPATH=. .

Corre las 3 etapas REALES (llamando al LLM) para el proyecto indicado y vuelca,
por etapa: input/validado. NO persiste en Mongo (solo lectura del proyecto).
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.database import get_mongo_config  # noqa: E402
from app.intelligence.factory import create_intelligence_service  # noqa: E402
from app.intelligence.pipeline import generate_project_fixed_proposal  # noqa: E402


HASH = os.getenv(
    "DEBUG_FILTER_LINK_HASH",
    "b58e79f568b127da365c67bb3cba6c6e2a979cc17529e8c5806beac7c4c015ea",
)


async def main() -> None:
    uri, db_name = get_mongo_config()
    host = uri.split("@")[-1].split("/")[0] if "@" in uri else uri
    print(f"=== MongoDB Atlas: {host} / db={db_name} ===")
    print(f"=== link_hash objetivo: {HASH} ===\n")

    # 1) Leer el proyecto (solo lectura)
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(uri)
    db = client[db_name]
    project = await db.projects.find_one({"link_hash": HASH})
    if not project:
        print("ERROR: proyecto no encontrado en Atlas.")
        return
    project["_id"] = str(project["_id"])
    print(f"Proyecto: {project.get('title')!r}")
    print(f"  contract_type : {project.get('contract_type')}")
    print(f"  status        : {project.get('proposal_status')}")
    print(f"  full_desc len : {len(project.get('full_description') or '')}")
    print()

    # 2) Construir adapters reales (segun providers/models en Atlas)
    adapters = await create_intelligence_service(db)
    print(f"Adapters: {list(adapters.keys())}")
    print()

    # 3) Correr el pipeline real (Etapa 1 -> 2 -> 3)
    try:
        result = await generate_project_fixed_proposal(
            project,
            standard_adapter=adapters["STANDARD"],
            premium_adapter=adapters["PREMIUM"],
        )
    except Exception as e:
        print(f"\n### PIPELINE FALLO: {type(e).__name__}: {e}")
        return

    # 4) Evaluar resultado por etapa
    print("\n================ RESULTADO ================")
    analysis = result.get("analysis", {})
    estimate = result.get("estimate", {})
    proposal = result.get("proposal", {})

    print("\n--- ETAPA 1 (analysis) ---")
    print(f"  maturity_score : {analysis.get('maturity_score')}")
    print(f"  branch         : {analysis.get('branch')}")
    print(f"  gaps           : {len(analysis.get('gaps', []))}")

    print("\n--- ETAPA 2 (estimate) ---")
    print(f"  estimate_type  : {estimate.get('estimate_type')}")
    print(f"  milestones     : {len(estimate.get('milestones', []))}")
    print(f"  summary        : {estimate.get('summary')}")
    if estimate.get("estimate_type") == "discovery":
        print(f"  discovery_hours: {estimate.get('discovery_hours')}")
        print(f"  scope in/out   : {len(estimate.get('scope_matrix', {}).get('in_scope', []))}"
              f"/{len(estimate.get('scope_matrix', {}).get('out_of_scope', []))}")
        print(f"  open_questions : {len(estimate.get('open_questions', []))}")

    print("\n--- ETAPA 3 (proposal) ---")
    print(f"  keys           : {sorted(proposal.keys())}")
    print(f"  has header     : {bool(proposal.get('proposal_header'))}")
    print(f"  milestones     : {len(proposal.get('milestones', []))}")

    print("\n--- JSON COMPLETO (acumulado) ---")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str)[:6000])

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
