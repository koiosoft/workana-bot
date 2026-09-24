"""Re-procesa UN proyecto end-to-end igual que ``/procesar`` del bot.

Replica el camino de ``handlers.process_projects`` para un unico ``link_hash``
(leido de ``DEBUG_FILTER_LINK_HASH``), SIN tocar el bot en vivo:

    1. Selecciona el proyecto con el MISMO criterio que el bot
       (analyzed + ai_score>=5 + full_description ausente).
    2. Re-scrapea el detalle (descripcion cruda real de Workana).
    3. Formatea la descripcion con el STANDARD adapter (fix ya aplicado).
    4. Persiste ``full_description`` formateado (Markdown).
    5. Genera y persiste la propuesta por etapas (servicio compartido).

Uso:
    DEBUG_FILTER_LINK_HASH=<hash> PYTHONPATH=. \
        .venv/bin/python scripts/reprocess_one_project.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.projects_repository import ProjectsRepository  # noqa: E402
from app.intelligence.factory import create_intelligence_service  # noqa: E402
from app.scraper.factory import ScraperFactory  # noqa: E402
from app.services.proposal_pipeline_service import (  # noqa: E402
    generate_and_persist_proposal,
)

load_dotenv()


async def main() -> None:
    link_hash = os.environ.get("DEBUG_FILTER_LINK_HASH", "").strip()
    if not link_hash:
        print("ERROR: define DEBUG_FILTER_LINK_HASH=<link_hash>")
        return

    repo = ProjectsRepository()
    project = await repo.collection.find_one({"link_hash": link_hash})
    if not project:
        print(f"ERROR: proyecto {link_hash} no encontrado.")
        return

    print(f"Proyecto : {project.get('title')!r}")
    print(f"status   : {project.get('proposal_status')}  score={project.get('ai_score')}")
    print(f"has fd   : {'full_description' in project}")
    print()

    # 1) Mismo criterio que get_projects_for_deep_analysis.
    eligible = (
        project.get("proposal_status") == "analyzed"
        and (project.get("ai_score") or 0) >= 5
        and "full_description" not in project
    )
    print(f"[1] ¿Elegible por el bot? {'SI' if eligible else 'NO'}")
    if not eligible:
        print("    (abortando: no cumple el criterio de seleccion)")
        return

    adapters = await create_intelligence_service()
    scraper = ScraperFactory.get_scraper()

    # 2) Re-scrape.
    print("[2] Re-scrapeando detalle...")
    full_detail = await scraper.fetch_full_detail(project.get("link"))
    if not full_detail:
        print("    ERROR: scrape vacio (page no encontrada / bloqueo).")
        return
    raw = full_detail.get("full_description") or ""
    print(f"    descripcion cruda: {len(raw)} chars")

    # 3) Formatear (fix aplicado).
    print("[3] Formateando descripcion (STANDARD)...")
    formatted = await adapters["STANDARD"].format_project_description(raw)
    print(f"    descripcion formateada: {len(formatted)} chars")
    print("    --- primeras lineas ---")
    for line in formatted.splitlines()[:14]:
        print("    |", line)
    full_detail["full_description"] = formatted

    # 4) Persistir.
    print("[4] Persistiendo full_description formateado...")
    await repo.update_full_details(link_hash, full_detail)

    # 5) Generar propuesta por etapas + persistir.
    full_detail.update(
        {
            "contract_type": project.get("contract_type", "project_fixed"),
            "strategy": project.get("strategy", "none"),
            "link_hash": link_hash,
            "title": project.get("title"),
        }
    )
    print("[5] Generando propuesta por etapas (project_fixed)...")
    result = await generate_and_persist_proposal(full_detail, adapters)
    if result and "error" not in result:
        print("    OK: propuesta generada y persistida.")
    else:
        print(f"    FALLO: {result.get('error') if result else 'None'}")

    # Estado final.
    fresh = await repo.collection.find_one({"link_hash": link_hash}, {"proposal_status": 1})
    print()
    print(f"status final: {fresh.get('proposal_status')}")


if __name__ == "__main__":
    asyncio.run(main())
