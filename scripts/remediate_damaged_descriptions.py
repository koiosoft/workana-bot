"""Remediacion quirurgica de proyectos con ``full_description`` dañado.

Contexto (bug de produccion)
----------------------------
El formateador de descripciones viajaba con ``response_format=json_object``
forzado, de modo que el LLM envolvia la prosa en un objeto JSON y ese
envoltorio se persistia como ``full_description``. Resultado: 79/115 proyectos
con descripcion inservible (``{"1":""}``, envoltorios vacios, eco de
instrucciones, prompt leak). Las propuestas generadas a partir de esos textos
son, por tanto, poco fiables.

El fix del pipeline ya esta aplicado (``description_sanitizer`` +
``json_mode=False`` + prompt Markdown). Este script pone los proyectos
afectados en el estado que el bot espera para **volver a correr el proceso**:

    ``process_projects`` selecciona proyectos con
        proposal_status == "analyzed"
        ai_score >= 5
        full_description inexistente
    (ver ``ProjectsRepository.get_projects_for_deep_analysis``)

Diferencia con ``scripts/reset_projects.py``
--------------------------------------------
``reset_projects.py`` resetea **por estado** (todo ``proposal_generated``),
sin mirar si la descripcion esta dañada: borraria propuestas buenas. Este script
detecta el daño **por dato** reutilizando ``classify_damaged_description`` (la
misma logica que el pipeline) y solo toca lo afectado.

Uso (SIEMPRE dry-run primero)
-----------------------------
    # Reporte (no modifica nada):
    docker exec workana_bot python -m scripts.remediate_damaged_descriptions --report

    # Reporte a archivo para revision:
    docker exec workana_bot python -m scripts.remediate_damaged_descriptions \
        --report --out /usr/src/app/.sdd/remediation_report.json

    # Aplicar (resetea los dañados para re-procesar):
    docker exec workana_bot python -m scripts.remediate_damaged_descriptions --apply

Seguridad
---------
- Dry-run es el modo por defecto.
- ``submited_to_workana`` NUNCA se toca salvo ``--include-submitted``.
- Las versiones previas NO se borran: se archivan con
  ``source_of_changes="BAD_DESCRIPTION_BACKUP"``.
- ``--bump-score`` garantiza ``ai_score >= MIN_SCORE`` para que el bot los tome
  (por defecto los ``analyzed`` dañados tienen score < 5 y quedarian fuera).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Permitir importes absolutos igual que main.py (local y Docker).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.intelligence.description_sanitizer import (  # noqa: E402
    classify_damaged_description,
    is_damaged_description,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Politica de remediacion
# ---------------------------------------------------------------------------

# Estados que se pueden resetear. ``submited_to_workana`` queda fuera salvo
# que se pase --include-submitted (esas propuestas ya se enviaron).
DEFAULT_STATUSES = ["proposal_generated", "analyzed", "not_found"]
NEVER_TOUCH_STATUSES = ["submited_to_workana"]

# Score minimo que exige ``get_projects_for_deep_analysis``.
MIN_SCORE = 5

# Colecciones derivadas a limpiar al resetear (se borran: son artefactos de la
# corrida con descripcion dañada; la propuesta util se ARCHIVA en
# proposal_versions, no se borra).
DERIVED_COLLECTIONS_TO_PURGE = ["requirement_analyses", "technical_estimates"]

# Etiqueta con la que se archivan las versiones previas.
BACKUP_SOURCE = "BAD_DESCRIPTION_BACKUP"


@dataclass
class ProjectReport:
    """Fila de reporte por proyecto afectado."""

    _id: str
    link_hash: str
    title: str
    proposal_status: str
    ai_score: Optional[float]
    damage: str
    full_description_preview: str
    proposal_versions: int = 0
    will_reset: bool = False
    bump_score: bool = False
    notes: list[str] = field(default_factory=list)


def _preview(value: Optional[str], n: int = 120) -> str:
    if not value:
        return ""
    return value.strip().replace("\n", "\\n")[:n]


async def _collect_report(
    db: Any,
    *,
    statuses: list[str],
    include_submitted: bool,
    bump_score: bool,
    link_hashes: Optional[list[str]] = None,
) -> list[ProjectReport]:
    """Recorre la coleccion y arma el reporte de proyectos afectados."""
    selected = list(statuses)
    if include_submitted:
        selected.extend(NEVER_TOUCH_STATUSES)

    query: dict[str, Any] = {
        "proposal_status": {"$in": selected},
        "deleted_at": {"$exists": False},
    }
    if link_hashes:
        query["link_hash"] = {"$in": link_hashes}

    reports: list[ProjectReport] = []
    async for doc in db.projects.find(query):
        damage = classify_damaged_description(doc.get("full_description"))
        if not is_damaged_description(doc.get("full_description")):
            continue  # sano: no se toca

        status = doc.get("proposal_status", "?")
        score = doc.get("ai_score")
        version_count = await db.proposal_versions.count_documents(
            {"link_hash": doc.get("link_hash")}
        )

        notes: list[str] = []
        will_reset = status in selected
        need_bump = bump_score and (score is None or score < MIN_SCORE)
        if need_bump:
            notes.append(f"ai_score {score!r} < {MIN_SCORE} -> se eleva")
        if status in NEVER_TOUCH_STATUSES:
            notes.append("SUBMITTED: requiere --include-submitted")

        reports.append(
            ProjectReport(
                _id=str(doc.get("_id")),
                link_hash=doc.get("link_hash", ""),
                title=doc.get("title", ""),
                proposal_status=status,
                ai_score=score,
                damage=damage,
                full_description_preview=_preview(doc.get("full_description")),
                proposal_versions=version_count,
                will_reset=will_reset,
                bump_score=need_bump,
                notes=notes,
            )
        )
    return reports


def _print_report(reports: list[ProjectReport]) -> None:
    from collections import Counter

    print(f"Proyectos dañados encontrados: {len(reports)}")
    print()
    print("Por tipo de daño:")
    for k, v in sorted(Counter(r.damage for r in reports).items(), key=lambda x: -x[1]):
        print(f"  {k:<20}: {v}")
    print()
    print("Por proposal_status:")
    for k, v in sorted(
        Counter(r.proposal_status for r in reports).items(), key=lambda x: -x[1]
    ):
        print(f"  {k:<22}: {v}")
    print()
    total_versions = sum(r.proposal_versions for r in reports)
    resetables = [r for r in reports if r.will_reset]
    bumps = [r for r in reports if r.bump_score]
    print(f"Versiones de propuesta asociadas (a archivar): {total_versions}")
    print(f"Proyectos a resetear: {len(resetables)}")
    print(f"Proyectos con ai_score a elevar: {len(bumps)}")
    print()
    print("Detalle:")
    for r in reports:
        flags = ""
        if r.bump_score:
            flags += " [bump-score]"
        if r.notes:
            flags += " [" + "; ".join(r.notes) + "]"
        print(f"  - {r.link_hash[:16]}… status={r.proposal_status:<18} "
              f"damage={r.damage:<17} score={r.ai_score}{flags}")
        print(f"      {r.title[:70]}")
        print(f"      fd={r.full_description_preview!r}")


async def _apply(
    db: Any,
    reports: list[ProjectReport],
    *,
    bump_score: bool,
) -> dict[str, int]:
    """Aplica la remediacion. Devuelve contadores."""
    resetables = [r for r in reports if r.will_reset]
    hashes = [r.link_hash for r in resetables if r.link_hash]
    stats = {"projects": 0, "versions_archived": 0}

    if not hashes:
        return stats

    # 1) Archivar versiones previas (NO borrar).
    arch = await db.proposal_versions.update_many(
        {"link_hash": {"$in": hashes}},
        {"$set": {"source_of_changes": BACKUP_SOURCE}},
    )
    stats["versions_archived"] = arch.modified_count

    # 2) Resetear los proyectos.
    now = datetime.now(timezone.utc).isoformat()
    res = await db.projects.update_many(
        {"link_hash": {"$in": hashes}},
        {
            "$set": {"proposal_status": "analyzed", "updated_at": now, "reset_at": now},
            "$unset": {
                "full_description": "",
                "proposal_at": "",
                "temp_proposal_data": "",
                "proposal_draft": "",
            },
        },
    )
    stats["projects"] = res.modified_count

    # 3) Elevar ai_score para que process_projects los tome.
    if bump_score:
        bump_hashes = [r.link_hash for r in reports if r.bump_score and r.link_hash]
        if bump_hashes:
            await db.projects.update_many(
                {"link_hash": {"$in": bump_hashes}},
                {"$set": {"ai_score": MIN_SCORE, "updated_at": now}},
            )

    # 4) Purgar artefactos derivados de la corrida dañada.
    for col in DERIVED_COLLECTIONS_TO_PURGE:
        await db[col].delete_many({"link_hash": {"$in": hashes}})

    return stats


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Remediacion de proyectos con full_description dañado."
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--report", action="store_true", help="Solo reporta (default)."
    )
    mode.add_argument(
        "--apply", action="store_true", help="Aplica la remediacion (modifica datos)."
    )
    p.add_argument(
        "--include-submitted",
        action="store_true",
        help="Incluye tambien proyectos 'submited_to_workana' (ya enviados).",
    )
    p.add_argument(
        "--bump-score",
        action="store_true",
        help=f"Eleva ai_score a {MIN_SCORE} cuando sea menor (para que el bot los tome).",
    )
    p.add_argument(
        "--status",
        action="append",
        default=None,
        help="Estado a considerar (repetible). Default: proposal_generated, analyzed, not_found.",
    )
    p.add_argument("--out", default=None, help="Escribe el reporte JSON a esta ruta.")
    p.add_argument("--limit", type=int, default=0, help="Limita N proyectos (0 = todos).")
    p.add_argument(
        "--link-hash",
        default=None,
        help="Uno o varios link_hash (separados por coma) para cirugia fina.",
    )
    return p.parse_args()


async def main() -> None:
    args = _parse_args()
    statuses = args.status or DEFAULT_STATUSES
    apply_changes = args.apply

    uri = os.getenv("MONGO_URI")
    db_name = os.getenv("MONGO_DB_NAME", "workana_bot")
    client = AsyncIOMotorClient(uri)
    db = client[db_name]

    host = uri.split("@")[-1].split("/")[0] if uri else "?"
    mode = "APPLY (modificara datos)" if apply_changes else "DRY-RUN (solo muestra)"
    print("=== Remediacion de descripciones dañadas ===")
    print(f"  Atlas  : {host} / db={db_name}")
    print(f"  Modo   : {mode}")
    print(f"  Estados: {statuses}" + ("  + submited_to_workana" if args.include_submitted else ""))
    print(f"  No se toca: {NEVER_TOUCH_STATUSES} (salvo --include-submitted)")
    print(f"  bump-score: {'si' if args.bump_score else 'no'}")
    print()

    link_hashes = None
    if args.link_hash:
        link_hashes = [h.strip() for h in args.link_hash.split(",") if h.strip()]
    reports = await _collect_report(
        db,
        statuses=statuses,
        include_submitted=args.include_submitted,
        bump_score=args.bump_score,
        link_hashes=link_hashes,
    )
    if args.limit and args.limit > 0:
        reports = reports[: args.limit]

    _print_report(reports)
    print()

    if args.out:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "total": len(reports),
            "projects": [asdict(r) for r in reports],
        }
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"Reporte escrito en: {args.out}")
        print()

    if not apply_changes:
        print("DRY-RUN: no se modifico nada. Re-ejecutar con --apply para aplicar.")
        client.close()
        return

    stats = await _apply(db, reports, bump_score=args.bump_score)
    print("=== Aplicado ===")
    print(f"  projects reseteados     : {stats['projects']}")
    print(f"  versions archivadas     : {stats['versions_archived']}")
    if args.bump_score:
        print(f"  ai_score elevados a >= {MIN_SCORE}")
    print()
    print("Siguiente paso: correr el bot (/process) para regenerar las propuestas.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
