# Sistema de Semáforo Global, Rollback Automático y Contingencia Operacional

## 📋 Tabla de Contenidos

1. [Visión General](#visión-general)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Componentes Principales](#componentes-principales)
4. [Flujos de Operación](#flujos-de-operación)
5. [Comandos Administrativos](#comandos-administrativos)
6. [Casos de Uso](#casos-de-uso)

---

## Visión General

Este sistema implementa un mecanismo robusto de control de concurrencia y resiliencia para el proceso de generación de propuestas en el bot de Workana. Los pilares fundamentales son:

- **Semáforo Global Persistente**: Control de concurrencia atómico en MongoDB
- **Rollback Automático**: Reversión limpia de estados ante fallos
- **Telemetría Avanzada**: Monitoreo en tiempo real del progreso
- **Comando de Escape**: Liberación manual ante fallas críticas

### Principios de Diseño

1. **Idempotencia**: Todas las operaciones pueden ejecutarse múltiples veces de forma segura
2. **Aislamiento**: Los errores en un proyecto no afectan al resto de la cola
3. **Resiliencia en Caliente**: El sistema puede recuperarse automáticamente de fallos
4. **Telemetría Transparente**: Visibilidad completa del estado del proceso

---

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                      Usuario Telegram                        │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  /procesar (Handler)  │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   Semáforo Global     │◄──── MongoDB (persistente)
        │   - acquire()         │
        │   - is_locked()       │
        │   - update_activity() │
        │   - release()         │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  Procesamiento        │
        │  - Scraping           │
        │  - Formateo IA        │
        │  - Generación Props   │
        └───────────┬───────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
    [Éxito]                [Fallo]
        │                       │
        ▼                       ▼
  [Guardado]           [Rollback a 'analyzed']
                              │
                              ▼
                    [Limpieza de datos parciales]
```

---

## Componentes Principales

### 1. ProcessSemaphore (`app/database/semaphore.py`)

Clase que gestiona el semáforo global persistente en MongoDB.

#### Métodos Clave

##### `acquire(total_projects: int) -> bool`
```python
# Intenta adquirir el semáforo de forma atómica
# Retorna True si se adquirió, False si ya está bloqueado
acquired = await semaphore.acquire(total_projects=50)
```

**Operación atómica**: Usa `update_one` con condición `$or` para garantizar que solo un proceso pueda adquirir el bloqueo.

##### `is_locked() -> bool`
```python
# Verifica si el semáforo está actualmente bloqueado
if await semaphore.is_locked():
    # Mostrar telemetría y abortar
    pass
```

##### `update_activity(processed, failed, not_found) -> bool`
```python
# Actualiza las métricas en tiempo real
await semaphore.update_activity(
    processed=10,
    failed=2,
    not_found=1
)
```

**Llamado después de cada proyecto**: Mantiene la telemetría fresca para el comando bloqueado.

##### `release() -> bool`
```python
# Libera el semáforo al finalizar (se ejecuta en bloque finally)
await semaphore.release()
```

##### `force_release() -> bool`
```python
# Liberación forzada administrativa (idempotente)
await semaphore.force_release()
```

##### `format_telemetry_message(status: dict) -> str`
```python
# Genera mensaje formateado con telemetría completa
message = semaphore.format_telemetry_message(status)
```

**Ejemplo de salida**:
```
🔒 **BLOQUEADO** - Generación de propuestas en ejecución

📅 **Bloqueado desde:** 2024-01-15 14:30:00 UTC
⏱️ **Última actividad:** 2024-01-15 14:45:23 UTC
📊 **Proyectos restantes:** 35/50

✅ Procesados: 12
❌ Fallidos: 2
🚫 No encontrados: 1
```

---

### 2. ProjectsRepository - Método `rollback_to_analyzed()`

Implementa el mecanismo de reversión limpia de estados.

```python
async def rollback_to_analyzed(self, link_hash: str) -> bool:
    """
    Realiza un rollback completo de un proyecto que falló durante 
    la generación de propuesta.
    """
    result = await self.collection.update_one(
        {"link_hash": link_hash},
        {
            "$set": {
                "proposal_status": "analyzed",
                "updated_at": now,
                "rollback_at": now
            },
            "$unset": {
                # Limpieza destructiva de datos parciales
                "proposal": "",
                "proposal_at": "",
                "temp_proposal_data": "",
                "proposal_draft": "",
                "corrupted_milestones": ""
            }
        }
    )
```

#### ¿Qué se conserva en el rollback?

- ✅ `full_description` (costoso de obtener)
- ✅ `budget_detail` (costoso de obtener)
- ✅ `ai_score` (análisis previo)
- ✅ `ai_summary` (análisis previo)
- ✅ `contract_type` (análisis previo)
- ✅ `strategy` (análisis previo)

#### ¿Qué se elimina en el rollback?

- ❌ `proposal` (datos corruptos o parciales)
- ❌ `proposal_at` (timestamp corrupto)
- ❌ Cualquier campo temporal o borrador

---

### 3. Handler `process_projects()` con Integración de Semáforo

#### Flujo de Ejecución

```python
async def process_projects(update, context):
    # FASE 1: VERIFICACIÓN DEL SEMÁFORO
    if await semaphore.is_locked():
        # Mostrar telemetría y abortar
        return
    
    # FASE 2: ADQUISICIÓN ATÓMICA
    if not await semaphore.acquire(total_projects=len(projects)):
        # Colisión detectada, abortar
        return
    
    try:
        # FASE 3: PROCESAMIENTO CON ROLLBACK
        for project in projects:
            needs_rollback = False
            
            try:
                # Scraping y actualización de detalles
                await update_full_details(...)
                needs_rollback = True  # Activar protección
                
                # Generación de propuesta (PUNTO CRÍTICO)
                proposal = await ai_service.generate_proposal(...)
                
                if proposal and "error" not in proposal:
                    # Éxito
                    await update_project_proposal(...)
                    needs_rollback = False
                else:
                    # Fallo de IA - ROLLBACK
                    if needs_rollback:
                        await rollback_to_analyzed(link_hash)
                
            except Exception as e:
                # Error de red/crítico - ROLLBACK
                if needs_rollback:
                    await rollback_to_analyzed(link_hash)
            
            # Actualizar telemetría después de cada proyecto
            await semaphore.update_activity(...)
    
    finally:
        # FASE 4: LIBERACIÓN GARANTIZADA
        await semaphore.release()
```

---

### 4. Comando `/desbloquear`

Handler administrativo de escape para liberar el semáforo manualmente.

```python
async def unlock_semaphore(update, context):
    """
    Comando de escape administrativo.
    Idempotente: puede ejecutarse en cualquier momento.
    """
    if not await is_admin(update):
        return
    
    status = await semaphore.get_status()
    was_locked = status.get("is_locked", False) if status else False
    
    # Liberación forzada (siempre exitosa)
    await semaphore.force_release()
    
    if was_locked:
        await update.message.reply_text(
            "🔓 **Semáforo Global liberado manualmente**\n"
            "El comando /procesar vuelve a estar disponible."
        )
    else:
        await update.message.reply_text(
            "ℹ️ El semáforo ya estaba liberado.\n"
            "Operación completada (idempotente)."
        )
```

---

## Flujos de Operación

### Flujo Normal (Sin Colisiones)

```
Usuario → /procesar
    ↓
Verificar semáforo (unlocked)
    ↓
Adquirir semáforo (success)
    ↓
Procesar proyectos (1/50, 2/50, ...)
    ├── Cada proyecto:
    │   ├── Scraping exitoso
    │   ├── Formateo IA exitoso
    │   ├── Generación propuesta exitosa
    │   └── Actualizar telemetría
    ↓
Liberar semáforo (finally)
    ↓
Reporte final
```

### Flujo con Colisión de Concurrencia

```
Usuario A → /procesar
    ↓
Adquirir semáforo (success)
    ↓
Procesando (locked)

Usuario B → /procesar (mientras A procesa)
    ↓
Verificar semáforo (locked) ❌
    ↓
Mostrar telemetría:
    - Bloqueado desde: [timestamp]
    - Última actividad: [timestamp]
    - Proyectos restantes: 35/50
    ↓
Abortar (sin conflicto)
```

### Flujo con Fallo y Rollback

```
Usuario → /procesar
    ↓
Proyecto #15 → Scraping OK
    ↓
Actualizar detalles (ready_for_proposal)
    ↓
[needs_rollback = True]
    ↓
Generación propuesta → FALLO ❌
    ↓
Ejecutar rollback:
    - Estado: ready_for_proposal → analyzed
    - Limpiar: proposal, proposal_at
    - Conservar: full_description, ai_score
    ↓
Continuar con proyecto #16
```

### Flujo de Escape Administrativo

```
Sistema congelado (3 horas sin actividad)
    ↓
Admin → /desbloquear
    ↓
force_release() (idempotente)
    ↓
Semáforo liberado
    ↓
/procesar disponible nuevamente
```

---

## Comandos Administrativos

### `/procesar`
- **Descripción**: Inicia el proceso de generación de propuestas
- **Protecciones**:
  - Verifica semáforo antes de iniciar
  - Adquiere semáforo de forma atómica
  - Libera semáforo en bloque `finally`
- **Telemetría**: Actualización en tiempo real después de cada proyecto

### `/desbloquear`
- **Descripción**: Libera el semáforo de forma manual (comando de escape)
- **Cuándo usar**:
  - Proceso congelado (>3 horas sin actividad)
  - Caída de infraestructura
  - Muerte del hilo sin ejecución del `finally`
- **Seguridad**: 
  - Solo accesible por admin
  - Operación idempotente (segura ejecutarla múltiples veces)
  - No corrompe datos de la base de datos

---

## Casos de Uso

### Caso 1: Ejecución Normal Completa

**Escenario**: Procesar 50 proyectos sin interrupciones

1. Usuario ejecuta `/procesar`
2. Semáforo se adquiere exitosamente
3. Cada proyecto se procesa secuencialmente:
   - Scraping → Formateo → Propuesta
   - Telemetría actualizada tras cada uno
4. Todos los proyectos completan
5. Semáforo se libera automáticamente
6. Reporte final enviado

**Resultado**: ✅ 50 procesados, 0 fallidos

---

### Caso 2: Intento de Ejecución Concurrente

**Escenario**: Dos administradores ejecutan `/procesar` simultáneamente

1. Admin A ejecuta `/procesar` → Adquiere semáforo ✅
2. Admin B ejecuta `/procesar` 5 segundos después
3. Semáforo detecta bloqueo existente
4. Admin B recibe mensaje de telemetría:
   ```
   🔒 BLOQUEADO - Generación en ejecución
   📅 Bloqueado desde: 2024-01-15 14:30:00 UTC
   ⏱️ Última actividad: 2024-01-15 14:30:05 UTC
   📊 Proyectos restantes: 48/50
   ```
5. Admin B no inicia procesamiento (sin colisión)

**Resultado**: ✅ Concurrencia controlada, sin duplicación

---

### Caso 3: Fallo de IA en Generación de Propuesta

**Escenario**: La IA falla al generar propuesta para proyecto #23

1. Procesando proyecto #23
2. Scraping exitoso → Estado cambia a `ready_for_proposal`
3. `needs_rollback` se activa (True)
4. Generación de propuesta falla (timeout de IA)
5. Se detecta el error y se ejecuta rollback:
   - Estado: `ready_for_proposal` → `analyzed`
   - Se elimina: datos parciales de propuesta
   - Se conserva: `full_description`, `ai_score`
6. Proyecto #23 queda listo para reintentar en futuro ciclo
7. Proceso continúa con proyecto #24

**Resultado**: ✅ Proyecto revertido limpiamente, cola no abortada

---

### Caso 4: Fallo de Red con Circuit Breaker

**Escenario**: Problemas de conectividad causan 5 fallos consecutivos

1. Procesando proyectos normalmente
2. Proyecto #40 falla (timeout de red)
   - Reintento 1: Falla
   - Reintento 2: Falla
   - Reintento 3: Falla
   - Rollback ejecutado, `consecutive_failures = 1`
3. Proyecto #41 falla inmediatamente: `consecutive_failures = 2`
4. Proyectos #42, #43, #44 también fallan
5. `consecutive_failures = 5` → Circuit Breaker se activa
6. Mensaje enviado: "🚨 CIRCUIT BREAKER ACTIVADO 🚨"
7. Proceso abortado de forma controlada
8. Semáforo liberado en `finally`

**Resultado**: ✅ Sistema protegido de saturación, estado consistente

---

### Caso 5: Proceso Congelado - Escape Administrativo

**Escenario**: Bot se congela por 3 horas sin liberar semáforo

1. Proceso `/procesar` inicia a las 14:00
2. Sistema se congela en proyecto #30
3. A las 17:00 (3 horas después), telemetría muestra:
   ```
   🔒 BLOQUEADO
   📅 Bloqueado desde: 2024-01-15 14:00:00 UTC
   ⏱️ Última actividad: 2024-01-15 14:15:00 UTC
   📊 Proyectos restantes: 20/50
   ```
4. Admin ejecuta `/desbloquear`
5. Semáforo se libera forzadamente
6. Mensaje: "🔓 Semáforo Global liberado manualmente"
7. `/procesar` vuelve a estar disponible

**Resultado**: ✅ Sistema recuperado sin corromper datos

---

### Caso 6: Rollback Múltiple en una Ráfaga

**Escenario**: 10 proyectos fallan durante generación de propuesta

1. Procesando batch de 50 proyectos
2. Proyectos #5, #12, #18, #23, #30, #35, #40, #45, #48, #50 fallan
3. Cada fallo activa rollback individual:
   - Estado revertido a `analyzed`
   - Datos parciales eliminados
   - Proyecto queda listo para reintento
4. Los 40 proyectos exitosos se completan
5. Reporte final:
   ```
   ✅ Propuestas generadas: 40
   ❌ Fallidos: 10
   Total: 50
   ```
6. Los 10 fallidos quedan en estado `analyzed` (limpios)

**Resultado**: ✅ Aislamiento de errores, datos consistentes

---

## Criterios de Aceptación Técnicos

### 1. Integridad de Base de Datos
✅ **Cumplido**: El rollback elimina todos los datos parciales mediante `$unset`, dejando el documento idéntico a uno recién analizado.

```javascript
// Estado después del rollback (verificable en MongoDB)
{
  "proposal_status": "analyzed",
  "ai_score": 7,
  "full_description": "...", // Conservado
  "proposal": undefined,      // Eliminado
  "proposal_at": undefined    // Eliminado
}
```

### 2. Frescura de la Telemetría
✅ **Cumplido**: `update_activity()` se llama después de cada proyecto procesado, actualizando `last_activity_at` en tiempo real.

```python
# Después de cada proyecto
await semaphore.update_activity(
    processed=processed_count,
    failed=failed_count,
    not_found=not_found_count
)
```

### 3. Idempotencia del Escape
✅ **Cumplido**: `force_release()` usa `upsert=True` y siempre retorna `True`. Puede ejecutarse múltiples veces sin efectos secundarios.

```python
result = await self.collection.update_one(
    {"lock_id": self.LOCK_ID},
    {"$set": {"is_locked": False, ...}},
    upsert=True  # Idempotente
)
```

---

## Monitoreo y Debugging

### Logs Clave

```python
# Adquisición de semáforo
logger.success(f"🔒 Semáforo global adquirido. Total proyectos: {total_projects}")

# Rollback ejecutado
logger.warning(f"🔄 ROLLBACK: Proyecto {link_hash} revertido a estado 'analyzed'")

# Liberación automática
logger.success("🔓 Semáforo global liberado automáticamente")

# Liberación manual
logger.warning("⚠️ Semáforo liberado manualmente por comando administrativo")
```

### Consultas MongoDB Útiles

```javascript
// Ver estado actual del semáforo
db.process_semaphore.findOne({lock_id: "proposal_generation_lock"})

// Contar proyectos listos para rollback
db.projects.countDocuments({proposal_status: "ready_for_proposal"})

// Ver proyectos que sufrieron rollback
db.projects.find({rollback_at: {$exists: true}})
```

---

## Diagrama de Estados de Proyecto

```
    pending
       ↓
  (análisis IA)
       ↓
   analyzed ←──────────────────┐
       ↓                       │
  (scraping profundo)          │ ROLLBACK
       ↓                       │ (si falla propuesta)
ready_for_proposal             │
       ↓                       │
  (generación propuesta)       │
       ↓                       │
       ├─→ [ÉXITO] → proposal_generated
       │
       └─→ [FALLO] ─────────────┘
```

---

## Conclusión

Este sistema proporciona:

1. **Control de Concurrencia Robusto**: Sin colisiones ni ejecuciones duplicadas
2. **Resiliencia Automática**: Rollback limpio ante fallos individuales
3. **Telemetría Transparente**: Visibilidad completa del progreso en tiempo real
4. **Escape Seguro**: Comando administrativo idempotente para recuperación manual
5. **Aislamiento de Errores**: Un fallo no compromete toda la cola

Todo bajo principios de **idempotencia**, **atomicidad** y **resiliencia en caliente**.
