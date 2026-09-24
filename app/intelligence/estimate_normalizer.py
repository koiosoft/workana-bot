"""Normalizacion determinista de la salida de Etapa 2 (estimacion tecnica).

Este modulo vive FUERA de los adapters porque la logica es **comun a todos los
providers** (OpenRouter, Gemini): el LLM de cualquiera de ellos puede omitir
campos o escribir las horas a ojo, y items de scope como objetos. Antes esta
logica estaba DUPLICADA en cada adapter; ahora hay un solo lugar.

El adapter solo llama a ``normalize_estimate_hours(raw_json)`` tras parsear el
JSON del LLM y ANTES de validar con Pydantic.
"""

from __future__ import annotations

import os
from typing import Any


def _rate() -> int:
    """Tarifa horaria de project_fixed (misma que usan las plantillas)."""
    return int(os.getenv("HOURLY_RATE_PROJECT_FIXED", "18"))


def normalize_estimate_hours(raw_json: dict, branch: str = "full") -> dict:
    """Normaliza de forma DETERMINISTA la salida de Etapa 2 *in place*.

    Reglas:
      - Claves de `tasks` -> se PRESERVAN (son el titulo visible). Solo se
        limpian espacios y, si dos colisionan, se sufija ` (2)`, ` (3)`...
        para no perder tareas.
      - `milestone.hours_with_overhead` = suma de sus tareas.
      - `milestone.subtotal` = horas x tarifa.
      - `summary` se CONSTRUYE entero (total_hours = suma de hitos, budget,
        weeks, rate). No se confia en lo que emita el LLM.
      - Fallbacks de la rama discovery (`discovery_hours`, tarifa, `open_questions`).
      - `scope_matrix` -> `List[str]` (aplana items `{"item": ...}`).

    Devuelve el mismo dict (mutado) para encadenar.
    """
    if not isinstance(raw_json, dict):
        return raw_json

    rate = _rate()

    # --- Milestones: horas y subtotales deterministas ---
    # La CLAVE de la tarea se PRESERVA tal como la emite el LLM: es el
    # titulo visible en el Dashboard (no un slug tecnico). Solo se limpian
    # espacios sobrantes y se deduplica si dos claves colisionan (el dict
    # no admite duplicados: sin esto se perderian tareas).
    calc_total_hours = 0
    for ms in raw_json.get("milestones", []) or []:
        if not isinstance(ms, dict):
            continue
        tasks = ms.get("tasks") or {}
        if isinstance(tasks, dict):
            norm_tasks: dict[str, Any] = {}
            for k, tv in tasks.items():
                nk = str(k).strip() or "tarea"
                base_nk = nk
                i = 2
                while nk in norm_tasks:
                    nk = f"{base_nk} ({i})"
                    i += 1
                norm_tasks[nk] = tv
            ms["tasks"] = norm_tasks
            total_ms = sum(
                (t.get("hours_with_overhead", 0) or 0)
                for t in norm_tasks.values() if isinstance(t, dict)
            )
        else:
            total_ms = ms.get("hours_with_overhead", 0) or 0
        ms["hours_with_overhead"] = total_ms
        ms["subtotal"] = total_ms * rate
        calc_total_hours += total_ms

    # --- Summary: lo construye el adapter, no el LLM ---
    # SIEMPRE se emite (es obligatorio en el contrato). Un discovery sin
    # hitos estimables (proyecto vacio / todo por descubrir) es un caso
    # LEGITIMO: summary en ceros, no ausente. Ausentarlo rompia la
    # validacion Pydantic ("summary Field required") y tumbaba la etapa 2.
    raw_json["summary"] = {
        "total_hours": calc_total_hours,
        "total_budget": round(calc_total_hours * rate, 2),
        "delivery_time_weeks": max(1, -(-calc_total_hours // 40)),
        "hourly_rate_applied": float(rate),
    }

    # --- Rama discovery: fallbacks ---
    if branch != "full":
        raw_json.setdefault("discovery_hours", 8)
        raw_json.setdefault("post_discovery_hourly_rate", float(rate))
        if not raw_json.get("open_questions"):
            raw_json["open_questions"] = [
                "Confirmar el alcance funcional y tecnico del proyecto antes de estimar."
            ]
        sm = raw_json.get("scope_matrix")
        if isinstance(sm, dict):
            for key in ("in_scope", "out_of_scope"):
                items = sm.get(key)
                if isinstance(items, list):
                    sm[key] = [
                        (i.get("item", "") if isinstance(i, dict) else i) for i in items
                    ]

    return raw_json
