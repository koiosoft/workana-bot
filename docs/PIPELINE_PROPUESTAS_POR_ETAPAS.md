# Feature: Pipeline de Propuestas por Etapas (project_fixed)

## 📋 Descripción General

El pipeline por etapas descompone la generación de una propuesta `project_fixed`
en **fases separadas por responsabilidad**, cada una con su propio modelo y su
propio guard rail de validación:

```
[ full_description del cliente ]
              │
              ▼
┌─────────────────────────────────┐
│ ETAPA 1: analyze-requirement.j2 │  Modelo STANDARD
│ - Extrae entidades y reglas     │
│ - Detecta vacíos / gaps         │
│ - Asigna maturity_score (1-10)  │
│ - Decide rama: full | discovery │
│ - Validación Pydantic           │
└─────────────────────────────────┘
              │  analysis
     ┌────────┴────────┐
     ▼                 ▼
┌──────────────┐  ┌────────────────────┐
│ ETAPA 2A     │  │ ETAPA 2B           │
│ estimate-    │  │ estimate-          │  Modelo STANDARD
│ full.j2      │  │ discovery.j2       │
│ Hitos+hora   │  │ Estima lo estimable│
│ +presupuesto │  │ + discovery pagado │
└──────────────┘  └────────────────────┘
     └────────┬────────┘
              │  estimate
              ▼
┌─────────────────────────────────┐
│ ETAPA 3: write-proposal.j2      │  Modelo PREMIUM
│ - Textos comerciales            │
│ - milestones/summary VERBATIM   │
└─────────────────────────────────┘
              │  proposal
              ▼
   [ proposal_versions ]  (source_of_changes="IA")
```

> `staff_augmentation` **NO** usa este pipeline: mantiene su ruta monolítica
> (`generate_proposal` → `write-proposal-staffing.j2`).

## 🎯 Objetivo

Separar **ingeniería (números)** de **redacción comercial (persuasión)**, con dos
beneficios:

1. **Guard rail económico:** la Etapa 3 (PREMIUM, 2 RPM / 35 s) solo se factura si
   las Etapas 1-2 (STANDARD, baratas) ya pasaron su validación. Nunca se gasta
   cuota PREMIUM con datos corruptos.
2. **Modelo por etapa:** la ingeniería usa un modelo rápido/barato; solo la
   redacción usa el modelo caro.

## 🏗️ Arquitectura

### Orquestador: `app/intelligence/pipeline.py` (NUEVO)

**Decisión clave:** el orquestador vive **fuera** de los adapters. Un adapter está
atado a **un** provider (Gemini u OpenRouter). Si el orquestador viviera dentro de
un adapter, las tres etapas forzarían el mismo provider.

```python
async def generate_project_fixed_proposal(
    project,
    standard_adapter,   # Etapa 1 + 2
    premium_adapter,    # Etapa 3
    circuit_breaker=None,
):
    analysis  = await standard_adapter.analyze_requirement(project, ...)   # Etapa 1
    estimate  = await standard_adapter.estimate_technical(project, analysis, ...)  # Etapa 2
    proposal  = await premium_adapter.write_commercial_proposal(project, estimate, ...)  # Etapa 3
    return {"analysis": analysis, "estimate": estimate, "proposal": proposal}
```

Esto habilita **provider distinto por etapa** (p. ej. Etapa 1-2 en Gemini, Etapa 3
en OpenRouter) sin cambiar más código. Hoy ambos son OpenRouter.

**Guard rail:** si Etapa 1 o 2 lanzan `PipelineError`, el orquestador aborta **antes**
de invocar la Etapa 3.

### Adaptadores (`openrouter.py` / `gemini.py`)

Implementan los tres métodos de etapa (`analyze_requirement`, `estimate_technical`,
`write_commercial_proposal`). El orquestador vive fuera, así que el método
`generate_project_fixed_proposal` **fue eliminado** de los adapters y del
`IntelligencePort` (era código muerto tras el rediseño).

### Handler (`app/bots/telegram/handlers.py`)

Inyecta los adapters correctos y persiste las 3 colecciones:

```python
accumulated = await generate_project_fixed_proposal(
    full_detail,
    standard_adapter=adapters["STANDARD"],
    premium_adapter=adapters["PREMIUM"],
    circuit_breaker=circuit_breaker,
)
# → persistencia de requirement_analyses / technical_estimates / proposal_versions
```

## 📐 Contratos de salida (Pydantic)

| Etapa | Modelo | Campos |
|---|---|---|
| 1 | `RequirementAnalysis` | `maturity_score`, `maturity_reason`, `entities`, `gaps`, `branch` |
| 2A | `TechnicalEstimateFull` | `milestones[]`, `summary{}` |
| 2B | `TechnicalEstimateDiscovery` | `milestones[]`, `summary{}`, `scope_matrix{}`, `discovery_hours`, `post_discovery_hourly_rate`, `open_questions[]` |
| 3 | (contrato `MilestoneProposal`) | `proposal_header`, `milestones[]` (verbatim), `summary{}` (verbatim), `technical_pitch`, `questions_for_client[]` |

### Diseño B — estimación parcial (rama discovery)

Cuando el requerimiento está parcialmente claro, la Etapa 2B produce **dos partes**:

1. **Lo que sí se estima:** `milestones` + `summary` (lo conocido y cotizable).
2. **Lo desconocido:** `scope_matrix` (dentro/fuera) + `discovery_hours` (reuniones/
   consultoría) + `post_discovery_hourly_rate` (trabajo posterior por horas).

> `summary.total_budget` cubre **solo** la parte estimable; el discovery se cotiza
> aparte (`discovery_hours` × tarifa).

`milestones` vacío es válido **solo** si no hay ninguna tecnología/entregable/dato
identificable (caso raro). La regla de estimabilidad mínima obliga a generar al
menos un hito base cuando hay algo concreto.

## 💰 Estimación: "Horas de IA Supervisada"

Las horas **NO** son horas de programar código a mano. Son **Horas de IA
Supervisada**: el tiempo humano dedicado a **dirigir y validar** un LLM. Cada tarea
desglosa 4 fases (visibles en la `description`):

1. **Prompting / arquitectura** — definir contexto y estructura.
2. **Generación e iteración** — ejecutar, probar, re-indicar.
3. **Auditoría / QA** — revisar lógica, seguridad, integración.
4. **Integración al sistema** — acoplar al software existente.

**NO se aplican** el overhead fijo (×1.25) ni los suelos rígidos (270 h) — eran
artefactos del modelo "humano programando". El resultado es un número **realista**.

### Tarifa configurable

La tarifa se lee del entorno (**`.env`**), no hardcodeada en las plantillas:

```
HOURLY_RATE_PROJECT_FIXED=18      # llave en mano
HOURLY_RATE_STAFF_AUGMENTATION=15  # outsourcing (normalmente menor)
POST_DISCOVERY_HOURLY_RATE=18
```

> ⚠️ Cambiar el `.env` requiere **recrear** el contenedor (`docker compose -f docker-compose.dev.yml up -d bot`),
> no basta `restart` (el `env_file` se lee al crear el contenedor).
>
> **Pendiente:** migrar la tarifa a una colección `settings` en BD (editable en runtime).

## 📦 Persistencia (3 colecciones)

| Colección | Contenido | Responsable |
|---|---|---|
| `requirement_analyses` | JSON de Etapa 1 (`analysis` + envelope) | handler |
| `technical_estimates` | JSON de Etapa 2 (`analysis` + `estimate` + envelope) | handler |
| `proposal_versions` | Propuesta final (`proposal_data` = contrato `MilestoneProposal`) | handler |

Sin versionado secuencial: el "último" se resuelve por `created_at DESC`.

## 🔍 Observabilidad: post-mortem

Se volca todo a **`logs/pipeline_debug.log`** (sink DEBUG dedicado, ver
`app/main.py`), sin afectar el log normal ni Telegram/API. Cada traza es
identificable y de una sola línea:

```
[PIPELINE][link_hash=<hash>][START] ...
[PIPELINE][link_hash=<hash>][ETAPA1][INPUT|RAW_RESPONSE|VALIDATED] ...
[PIPELINE][link_hash=<hash>][ETAPA2][DRIVERS|INPUT|RAW_RESPONSE|VALIDATED] ...
[PIPELINE][link_hash=<hash>][ETAPA3][INPUT|RAW_RESPONSE|VALIDATED] ...
[PIPELINE][link_hash=<hash>][STAGE_DONE] etapa=N
[PIPELINE][link_hash=<hash>][STAGE_FAILED] etapa=N error=...
```

> Las trazas `[PIPELINE]` existen en **ambos adapters** (`openrouter.py` y
> `gemini.py`), en las 3 etapas (INPUT / RAW_RESPONSE / VALIDATED).

## 🧭 Flujo del handler (resumen)

1. Scrapea el detalle del proyecto (`fetch_full_detail`).
2. Formatea la descripción (`format_project_description`).
3. Marca el proyecto con `full_description` y `contract_type`.
4. `project_fixed` → `generate_project_fixed_proposal`; `staff_augmentation` → `generate_proposal`.
5. Si el pipeline tuvo éxito, persiste las 3 colecciones y marca `proposal_generated`.

## ⚠️ Notas de operación

- **Filtro de desarrollo:** `DEBUG_FILTER_LINK_HASH=<link_hash>` restringe el
  procesamiento a un solo proyecto (útil para pruebas aisladas).
- **Reprocesar un proyecto:** el bot solo toma los que están en
  `proposal_status: "analyzed"` **y** `full_description` **ausente** (marcador de
  "ya enriquecido"). Para repetir una prueba hay que revertir el status y borrar
  `full_description`.
- **Reinicio (IMPORTANTE):** el código va por **volumen**, y `docker compose up -d`
  **NO recarga** si la config del compose no cambió (reporta `Running`, no toca el
  proceso). Para recargar de verdad:
  - **Solo código / plantillas `.j2`** → **`docker compose -f docker-compose.dev.yml restart bot`** (reinicia el
    proceso y recarga el módulo).
  - **Cualquier cambio (código o `.env`)** → **`docker compose -f docker-compose.dev.yml down bot && docker
    compose up -d app`** (elimina y recrea el contenedor). Esta es la forma segura.
  - ⚠️ **Nunca** uses `docker compose -f docker-compose.dev.yml up -d bot` **solo** esperando recargar: no lo hace
    si la config no cambió.

## 🧪 Cobertura de tests

| Test | Cubre |
|---|---|
| `tests/unit/intelligence/test_pipeline.py` | Asignación de adapters por etapa, guard rail, providers mixtos |
| `tests/unit/models/test_estimate.py` | Contrato `TechnicalEstimateDiscovery` (Diseño B) |
| `tests/unit/database/test_technical_estimates_repository.py` | Persistencia discovery |
| `tests/unit/bots/test_telegram_handlers.py` | Ruteo por `contract_type` |
| `tests/integration/pipeline/test_project_fixed_pipeline.py` | Flujo completo del pipeline |

## 📌 Deuda / pendientes

- **Refine:** `refine-proposal.j2` reestima + redacta en **una** llamada PREMIUM;
  no separa etapas ni valida Pydantic. Decidir si debe pasar por el orquestador.
- **Tarifa en BD** (`settings`).
- **`gemini.py`:** ✅ instrumentado con trazas `[PIPELINE]` (hecho).
- **Persistencia intermedia:** todo-o-nada al final; un fallo en Etapa 3 pierde las
  intermedias. No hay reanudación.
- **Rama `full`:** validada con script, pendiente de prueba E2E vía bot.
