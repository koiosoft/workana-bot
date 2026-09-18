# Plan: Pipeline de Generación de Propuestas por Etapas (v2)

## 1. Objetivo
Línea de prueba

Refactorizar el proceso de generación de propuestas para `project_fixed`,
separando la **estimación técnica** (ingeniería, números) de la **redacción
comercial** (tono, persuasión), mediante un pipeline de 4 etapas impulsado por
un nuevo `maturity_score`.

`staff_augmentation` **NO cambia** (mantiene su ruta propia).

---

## 2. Decisiones tomadas

| # | Decisión |
|---|----------|
| 1 | `maturity_score` (1-10) mide madurez/detalle del **requerimiento**. Es un eje **nuevo**, independiente de `ai_score` (que sigue filtrando "¿merece atención?"). |
| 2 | La estimación técnica va en **STANDARD**. Solo la redacción comercial va en **PREMIUM**. |
| 3 | `staff_augmentation` queda **igual** (sin etapas 2A/2B, sin hitos). |
| 4 | El JSON técnico intermedio se **persiste** en colecciones propias (uso síncrono inicial, reutilizable a futuro). **Sin versionado secuencial** — el último registro por `project_id` se obtiene por `created_at DESC`. |
| 5 | Se implementan las **4 etapas completas**. |
| 6 | La propuesta final **sigue en `proposal_versions`** (sin cambios). Los artefactos intermedios van a colecciones propias; la trazabilidad entre ellos se resuelve por `project_id`/`link_hash` (**sin enlaces directos entre colecciones**). |
| 7 | Prompts con **subcarpetas por etapa** y prefijos semánticos (`analyze-`, `estimate-`, `write-`, `refine-`, `evaluate-`, `format-`). |
| 8 | Renombrado de prompts de **una vez** (sin alias de compatibilidad). |
| 9 | `write-proposal.j2` es **100% redacción persuasiva**; no altera números ni horas de la Etapa 2. |
| 10 | Threshold `maturity_score` configurable por variable de entorno (`MATURITY_THRESHOLD`, default `8`). |

---

## 3. Restricción fundamental: interfaces externas intactas

**Las capas de comunicación externa NO cambian:**

- **API REST (FastAPI):** mismo endpoint `GET /api/projects/{id}`, mismo
  `POST /{projectId}/refine`. La respuesta sigue incluyendo la propuesta en el
  mismo formato (`proposal` embebido). Los nuevos artefactos intermedios
  (`requirement_analyses`, `technical_estimates`) **no se exponen** por la API.
- **Bot de Telegram:** mismos comandos `/analizar`, `/procesar`, `/refinar`.
  Los mensajes de telemetría mantienen su estructura actual.

Todo el nuevo pipeline es **interno** a la capa de inteligencia y repositorios.

---

## 4. Pipeline de 4 Etapas (solo `project_fixed`)

```text
        [ full_description del cliente ]
                     │
                     ▼
  ┌─────────────────────────────────────────────┐
  │ ETAPA 1: analyze-requirement.j2             │   Modelo STANDARD
  │ - Extrae entidades y reglas de negocio       │
  │ - Identifica vacíos / incertidumbres         │
  │ - Asigna maturity_score (1-10)               │
  │ - Salida validada con Pydantic               │
  └─────────────────────────────────────────────┘
                     │
      ┌──────────────┴───────────────┐
      ▼                              ▼
  maturity_score >= T          maturity_score < T
   (Maduro)                      (Ambiguo)
      │                              │
      ▼                              ▼
┌──────────────────┐     ┌────────────────────────┐
│ ETAPA 2A         │     │ ETAPA 2B               │
│ estimate-full.j2 │     │ estimate-discovery.j2  │
│ - Desglose horas │     │ - Matriz Alcance SÍ/NO │   Modelo STANDARD
│ - Hitos y arq.   │     │ - Horas Fase 0         │
│ - Testing/deploy │     │ - Tarifa post-Discovery│
│ - Salida validada│     │ - Salida validada       │
└──────────────────┘     └────────────────────────┘
      │                              │
      └──────────────┬───────────────┘
                     │ (JSON técnico validado: hitos + horas + alcance)
                     ▼
  ┌─────────────────────────────────────────────┐
  │ ETAPA 3: write-proposal.j2                  │   Modelo PREMIUM
  │ - Recibe el JSON técnico de la Etapa 2       │
  │ - Aplica base-role (perfil senior)           │
  │ - Traduce números → pitch persuasivo + CTA   │
  │ - NO altera horas, precios ni hitos          │
  │ - Entrada garantizada válida (Etapa 2 pasó)  │
  └─────────────────────────────────────────────┘
                     │
                     ▼
        [ proposal_versions ] (source_of_changes="IA")
                     │
                     ▼
  ┌─────────────────────────────────────────────┐
  │ ETAPA 4: refine-proposal.j2 (under demand)  │
  └─────────────────────────────────────────────┘
```

> `T` = `MATURITY_THRESHOLD` leído de variable de entorno (default `8`).

### Evolución del JSON por etapas (enfoque acumulativo)

Cada etapa **enriquece** el artefacto de la etapa anterior en lugar de producir
un documento aislado. El JSON que viaja por el pipeline es **acumulativo**:

```text
Etapa 1 → { "analysis": { "maturity_score": 8, "entities": {...}, "gaps": [] } }
Etapa 2 → { "analysis": {...}, "estimate": { "milestones": [...], "summary": {...} } }
Etapa 3 → { "analysis": {...}, "estimate": {...},
            "proposal": { "proposal_header": "...", "technical_pitch": "...",
                          "questions_for_client": [...] } }
```

Esto significa:
- El JSON de la Etapa 1 es **input + base** para la Etapa 2.
- El JSON de la Etapa 2 es **input + base** para la Etapa 3.
- El registro persistido en cada colección refleja el JSON acumulado hasta
  esa etapa (cada registro es autocontenido).
- `technical_estimates` incluye `analysis` como subdocumento anidado.
- `proposal_versions.proposal_data` es el JSON final (Etapas 1+2+3), que
  sigue el contrato `MilestoneProposal` existente.

---

## 5. Renombrado de Prompts (corte limpio)

### Estructura nueva

```text
app/intelligence/prompts/
├── base/
│   └── base-role.j2                      # antes: base_role.j2
├── s1-analysis/
│   ├── evaluate-project.j2               # antes: evaluation.j2
│   └── format-description.j2             # antes: project_formatter.j2
├── s2-estimation/
│   ├── analyze-requirement.j2            # NUEVO (Etapa 1 del pipeline)
│   ├── estimate-full.j2                  # NUEVO (Etapa 2A)
│   └── estimate-discovery.j2             # NUEVO (Etapa 2B)
├── s3-commercial/
│   ├── write-proposal.j2                 # antes: proposal.j2
│   └── write-proposal-staffing.j2        # antes: proposal_staffing.j2
└── s4-refine/
    ├── refine-proposal.j2                # antes: refine.j2
    └── refine-proposal-staffing.j2       # antes: refine-staffing.j2
```

> La Etapa 1 (`analyze-requirement`) vive en `s2-estimation/` por ser el
> prerrequisito de la estimación (2A/2B). `s1-analysis/` agrupa el triaje
> previo (evaluación + formateo) que ya existe.

### Impacto del renombrado (referencias a actualizar)

- `app/intelligence/adapters/gemini.py` (líneas ~90, ~170, ~271-297, ~366)
- `app/intelligence/adapters/openrouter.py` (líneas ~226, ~310, ~418-444, ~523)
- `app/intelligence/factory.py` (`select_initial_proposal_template`, ~84-89)
- `tests/unit/intelligence/test_adapters.py`
- `tests/unit/intelligence/test_factory.py`
- `tests/unit/intelligence/test_gemini_adapter.py`
- `tests/integration/api/test_proposals.py` (líneas ~526-669)
- `docs/CONTRACT_TYPE_FEATURE.md`
- `docs/USAGE_EXAMPLES.md`

**Nota:** los loaders Jinja (`FileSystemLoader`) apuntan al directorio raíz
`prompts/`; los `get_template("<sub>/<nombre>.j2")` deben incluir la subcarpeta.

---

## 6. Modelo de Datos (colecciones nuevas, sin tocar las existentes)

Se mantienen intactas: `projects`, `proposal_versions`.

### 6.1 `requirement_analyses` (Etapa 1)

Persiste el análisis de madurez del requerimiento. **Sin versionado secuencial**;
el "último análisis" se determina por `created_at DESC`.

Contiene el **JSON acumulado de Etapa 1** (servirá de base para Etapa 2).

```jsonc
{
  "_id": ObjectId,
  "project_id": "string",           // _id del proyecto
  "link_hash": "string",
  "analysis": {                     // ← JSON acumulado de Etapa 1
    "maturity_score": 7,            // 1-10, entero
    "maturity_reason": "string",
    "entities": {                   // entidades extraídas
      "technologies": [],
      "deliverables": [],
      "constraints": []
    },
    "gaps": [],                     // vacíos/incertidumbres detectadas
    "branch": "full" | "discovery"  // decisión de bifurcación (≥T vs <T)
  },
  "maturity_threshold_used": 8,     // valor de T usado en esta evaluación
  "model_used": "string",
  "created_at": ISODate
}
```

Índices: `project_id + created_at DESC`, `link_hash`.

### 6.2 `technical_estimates` (Etapa 2A / 2B)

Persiste la estimación técnica pura (sin redacción comercial). **Sin versionado
secuencial**; la estimación vigente se determina por `created_at DESC`.

Contiene el **JSON acumulado de Etapa 1 + Etapa 2** (servirá de base para Etapa 3).

```jsonc
{
  "_id": ObjectId,
  "project_id": "string",
  "link_hash": "string",
  "estimate_type": "full" | "discovery",
  // Subdocumento anidado: analysis de la Etapa 1
  "analysis": {
    "maturity_score": 7,
    "entities": { ... },
    "gaps": [],
    "branch": "full"
  },
  // --- Si branch "full" (2A) ---
  "milestones": [
    {
      "step": 1,
      "name": "string",
      "tasks": {
        "Nombre tarea": { "description": "string", "hours_with_overhead": 12 }
      },
      "hours_with_overhead": 12,
      "subtotal": 300.0
    }
  ],
  "summary": {
    "total_hours": 220,
    "total_budget": 5500.0,
    "delivery_time_weeks": 8,
    "hourly_rate_applied": 25.0
  },
  // --- Si branch "discovery" (2B) ---
  "scope_matrix": {
    "in_scope": [ "string" ],
    "out_of_scope": [ "string" ]
  },
  "phase0_hours": 16,
  "post_discovery_hourly_rate": 25.0,
  "open_questions": [ "string" ],
  // --- Común ---
  "model_used": "string",
  "created_at": ISODate
}
```

Índices: `project_id + created_at DESC`, `link_hash`.

### 6.3 Trazabilidad entre colecciones

**No hay campos de enlace en `proposal_versions`.** La trazabilidad se resuelve
vía `project_id`/`link_hash`:

- `projects` → (1:N) → `requirement_analyses` (último por created_at DESC)
- `projects` → (1:N) → `technical_estimates` (último por created_at DESC)
- `projects` → (1:N) → `proposal_versions` (último por version_number DESC)

Para auditoría humana, cada documento lleva `created_at` e `model_used`.
El orden temporal es suficiente para reconstruir la secuencia de eventos.

---

## 7. Capa de Adaptadores (IntelligencePort)

### 7.1 Métodos nuevos en `IntelligencePort`

```python
async def analyze_requirement(
    self, project: dict,
    maturity_threshold: int = 8,
    circuit_breaker: CircuitBreaker | None = None
) -> dict[str, Any]: ...

async def estimate_technical(
    self, project: dict, analysis: dict,
    circuit_breaker: CircuitBreaker | None = None
) -> dict[str, Any]: ...

async def write_commercial_proposal(
    self, project: dict, technical_estimate: dict,
    circuit_breaker: CircuitBreaker | None = None
) -> dict[str, Any]: ...
```

### 7.2 Asignación de modelos

| Etapa | Adaptador | Modelo |
|-------|-----------|--------|
| 1 (analyze) | STANDARD | flash |
| 2A/2B (estimate) | STANDARD | flash |
| 3 (write) | PREMIUM | pro |
| 4 (refine) | STANDARD (selección por modelo) | según request |
| Staff Aug (directo) | PREMIUM | pro (sin cambios) |

### 7.3 Validación estricta de salidas JSON (guard rail)

**Las Etapas 1 y 2 son gatekeepers críticos.** Si su salida no es JSON válido
según el esquema Pydantic, el pipeline se detiene antes de gastar cuota PREMIUM.

**Mecanismo:**

1. **Modelos Pydantic dedicados** en `app/models/`:
   - `app/models/analysis.py` : `RequirementAnalysis`, `Entities`
   - `app/models/estimate.py` : `TechnicalEstimateFull`, `TechnicalEstimateDiscovery`,
     y reutiliza `Milestone`, `Task`, `MilestoneProposalSummary` de `project.py`.

2. **Usar `response_mime_type='application/json'`** donde el proveedor LLM lo
   soporte (Gemini lo admite nativamente como respuesta estructurada; para
   OpenRouter la validación es post-hoc).

3. **Validación inmediata post-parse con `model_validate`**:

   ```python
   from pydantic import ValidationError
   from app.models.analysis import RequirementAnalysis

   data = self._parse_json(raw_response)
   try:
       validated = RequirementAnalysis.model_validate(data)
   except ValidationError as e:
       logger.error(f'Etapa 1: JSON inválido - {e}')
       raise PipelineError('analyze-requirement: output fuera de esquema')
   ```

4. **Interrupción temprana del pipeline**:

   ```python
   async def generate_project_fixed_proposal(self, project, circuit_breaker=None):
       analysis = await self.analyze_requirement(...)  # raise → stop si falla validación
       estimate = await self.estimate_technical(...)    # raise → stop si falla validación
       # Solo llegamos aquí si Etapa 1 y 2 fueron exitosas
       proposal = await self.write_commercial_proposal(...)
       return proposal
   ```

Esto garantiza que **nunca** se invoca PREMIUM (2 RPM, 35s de delay) con datos
corruptos provenientes de STANDARD.

### 7.4 Estrategia de orquestación

- `generate_proposal()` se mantiene para `staff_augmentation` (ruta directa).
- Para `project_fixed` se introduce un orquestador interno:

```python
async def generate_project_fixed_proposal(
    self, project: dict, circuit_breaker=None
) -> dict:
    """Orquesta Etapa 1 → 2 → 3 para project_fixed.
    Cada etapa recibe el JSON acumulado de la etapa anterior.
    Si Etapa 1 o 2 fallan validación → raise → no se ejecuta Etapa 3.
    Retorna solo el JSON comercial final (proposal)."""
    threshold = int(os.getenv("MATURITY_THRESHOLD", "8"))
    analysis = await self.analyze_requirement(
        project, maturity_threshold=threshold, circuit_breaker=circuit_breaker
    )
    estimate = await self.estimate_technical(
        project, analysis, circuit_breaker=circuit_breaker
    )
    proposal = await self.write_commercial_proposal(
        project, estimate, circuit_breaker=circuit_breaker
    )
    return proposal
```

> El handler decide la ruta según `contract_type`:
> - `staff_augmentation` → `generate_proposal()` (ruta actual)
> - `project_fixed` → `generate_project_fixed_proposal()` (pipeline nuevo)

---

## 8. Configuración

```python
# .env o variable de entorno
MATURITY_THRESHOLD=8        # default: 8
```

El threshold se lee al iniciar el pipeline y se pasa como argumento a
`analyze_requirement` para que decida la bifurcación 2A vs 2B. También se
persiste en `requirement_analyses.maturity_threshold_used` para auditoría.

---

## 9. Cambios por archivo (implementación)

### 9.1 Renombrado (mecánico)
- `git mv` de los 7 templates a la nueva estructura de subcarpetas.
- Actualizar todas las referencias de templates listadas en §5.

### 9.2 Modelos Pydantic (nuevos)
- `app/models/analysis.py` : `RequirementAnalysis`, `Entities`, `Gap`, etc.
- `app/models/estimate.py` : `TechnicalEstimateFull`, `TechnicalEstimateDiscovery`.
  Reutiliza `Milestone`, `Task`, `MilestoneProposalSummary` de `project.py`.

### 9.3 Templates nuevos y refactor (prompts)
- `app/intelligence/prompts/s2-estimation/analyze-requirement.j2` (NUEVO)
  - Hereda de `base/base-role.j2`.
  - Recibe `full_description` y `threshold`.
  - Salida: `maturity_score` (1-10 int), `maturity_reason`, `entities`, `gaps`, `branch`.
- `app/intelligence/prompts/s2-estimation/estimate-full.j2` (NUEVO)
  - Extraer lógica de estimación de `proposal.j2` (270h mínimo, hitos, suelos técnicos).
  - Entrada: `analysis_json`. Salida: `milestones[]`, `summary{}` (sin texto comercial).
- `app/intelligence/prompts/s2-estimation/estimate-discovery.j2` (NUEVO)
  - Modo ambiguo: `scope_matrix{in_scope,out_of_scope}`, `phase0_hours`,
    `post_discovery_hourly_rate`, `open_questions`.
  - Entrada: `analysis_json`.
- `app/intelligence/prompts/s3-commercial/write-proposal.j2` (refactor de `proposal.j2`)
  - **100% redacción persuasiva**. Entrada: `technical_estimate_json`.
  - Horas/hitos/precios tomados tal cual del JSON, no recalcula.
  - Salida: `proposal_header`, `technical_pitch`, `questions_for_client`.
  - Mantiene maquetación `\n\n` y CTA condicional.

### 9.4 Adaptadores (`gemini.py` / `openrouter.py`)
- Actualizar `get_template("s2-estimation/...")` (subcarpetas).
- Añadir `analyze_requirement`, `estimate_technical`, `write_commercial_proposal`.
- Incorporar validación Pydantic post-parse en Etapas 1 y 2.
- Gemini: `response_mime_type='application/json'` en Etapas 1 y 2.
- Mantener `generate_proposal` (staff aug) y `refine_proposal`.
- Añadir `generate_project_fixed_proposal` (orquestador).

### 9.5 `app/intelligence/port.py`
- Añadir los 3 métodos abstractos.

### 9.6 `app/intelligence/factory.py`
- Actualizar `select_initial_proposal_template` a rutas con subcarpeta.
- Helper `select_estimation_template(maturity_score)`.

### 9.7 Repositorios nuevos
- `app/database/requirement_analyses_repository.py`
- `app/database/technical_estimates_repository.py`
- Ambos con `insert_X()` y `get_latest_by_project_id()` (sin versionado).

### 9.8 `app/bots/telegram/handlers.py`
- Bifurcar por `contract_type`:
  - `project_fixed` → `generate_project_fixed_proposal()` + persistir 3 colecciones.
  - `staff_augmentation` → ruta actual.
- Mensajes de telemetría sin cambios.

### 9.9 Tests
- Referencias de templates actualizadas.
- Tests unitarios: 3 métodos nuevos + validación Pydantic.
- Tests repositorios (sin versionado).
- Test integración pipeline completo `project_fixed`.
- Test validación: JSON inválido → raise → no PREMIUM.
- Test regresión: `staff_augmentation` intacto.

### 9.10 Docs
- Actualizar `docs/CONTRACT_TYPE_FEATURE.md` y `docs/USAGE_EXAMPLES.md`.
- Nuevo doc del pipeline por etapas.

---

## 10. Riesgos y consideraciones

1. **Rate limits PREMIUM (2 RPM / 35s):** el pipeline añade llamadas, pero solo
   la Etapa 3 es PREMIUM + staff aug. Las etapas 1-2 (STANDARD) son baratas/rápidas.
2. **Costo:** Etapa 1+2 usan flash; solo Etapa 3 usa pro → incremento contenido.
3. **Validación estricta:** el guard rail con Pydantic en Etapas 1 y 2 protege
   contra malgastar cuota PREMIUM con entradas inválidas.
4. **Idempotencia/reintentos:** si Etapa 3 falla, la estimación (Etapa 2) ya está
   persistida y es reutilizable. No se repite Etapas 1-2.
5. **Compatibilidad externa:** API REST y Telegram bot no cambian; cero impacto
   para consumidores.
6. **Migración:** no requiere backfill; solo prompts y código nuevo.
7. **Rollback semáforo:** se mantiene el mecanismo actual.

---

## 11. Orden de ejecución sugerido

1. Renombrado de prompts + actualización de referencias (corte limpio).
2. Modelos Pydantic (analysis + estimate) + repositorios nuevos.
3. Templates nuevos (analyze/estimate) y refactor de write-proposal.
4. `IntelligencePort` + métodos nuevos en adapters + guard rail de validación.
5. `factory.py` + `handlers.py` (solo bifurcación, sin cambiar interfaces).
6. Tests (unit → integración → validación).
7. Docs.