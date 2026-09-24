# Deploy & Production Protocol

> **Modelo:** el servidor de producción corre SIEMPRE la rama `stable`.
> Actualizar producción = `git pull stable` + rebuild. **Nunca se especifica rama.**
> Probar cambios sin afectar producción se hace en `stage` (rama `main`).

## Contexto

- **Prod**: servidor Ubuntu remoto, Docker. Sigue `stable`. Ver `docker-compose.prod.yml`.
- **Stage**: rama `main`, `.env.stage`, BD y sesión separadas. No toca prod.
- **Release**: `main` → `stable` vía `.sdd/core/git/RELEASE.md` (scripts de git).
- **Deploy**: `stable` → servidor vía `scripts/devops/` (este protocolo).

Artefactos:
```
docker-compose.prod.yml          # manifiesto de produccion (versionado)
.env.prod.example                # plantilla de variables (sin secretos)
scripts/devops/check_prod.sh     # preflight (solo lee)
scripts/devops/deploy_prod.sh    # deploy (pull stable + build + up + healthcheck)
scripts/devops/rollback_prod.sh  # revertir a un commit anterior
```

---

## Reglas Mandatorias

1. **SIEMPRE** ejecutar `check_prod.sh` (preflight) antes de desplegar. Si falla, **STOP**.
2. **NUNCA** usar `docker compose down -v` ni borrar volúmenes (`data/db`, `browser_data`).
3. **NUNCA** commitear el `.env` real (solo `.env.prod.example`).
4. Los **secretos** los aporta el humano en el servidor. El agente **verifica que existan**, no los crea.
5. Si el deploy falla el healthcheck, **rollback automático** (ya integrado en `deploy_prod.sh`).
6. Ante cualquier error de permisos o git, **DETENERSE y avisar** al humano (no auto-arreglar).

---

## Workflow de Ejecución

### Paso 1 — Preflight (obligatorio, solo lectura)
Ejecutar SOLO:
```
./scripts/devops/check_prod.sh
```
Evaluar la salida. Si algún chequeo es ❌ → **STOP** y reportar al usuario qué falta
(ramas, docker, `.env`, `state.json`, acceso a origin). NO continuar.

### Paso 2 — Confirmación del usuario
Mostrar al usuario:
- El commit actual del clon de prod y el de `origin/stable` (qué se va a desplegar).
- El resultado del preflight.
- Preguntar: *"¿Desplegar `stable` a producción ahora? (YES/NO)"*.

### Paso 3 — Deploy
Solo tras confirmación explícita:
```
./scripts/devops/deploy_prod.sh
```
El script hace: fetch + ff a `origin/stable` → `compose build` → `compose up -d` →
healthcheck → **rollback automático** si algo no arranca.

### Paso 4 — Verificación
- Confirmar contenedores `running`: `workana_bot`, `workana_api`.
- Mostrar `docker compose -f docker-compose.prod.yml logs --tail=50` para validar que
  no hay errores de arranque.
- Reportar versión desplegada (`git rev-parse --short HEAD`).

### Paso 5 — Rollback (si el usuario lo pide o el deploy quedó inestable)
```
./scripts/devops/rollback_prod.sh            # al commit anterior
./scripts/devops/rollback_prod.sh v1.2.3     # a un tag/commit especifico
```

---

## Diferencias dev vs prod (no confundir)

| | Dev (`docker-compose.yml`) | Prod (`docker-compose.prod.yml`) |
|---|---|---|
| Código | bind-mount `./app` (working tree) | **imagen inmutable** (build desde `stable`) |
| Env | `.env` + `.env.stage` | `.env` (prod) |
| Rama | `main` (trabajo) | `stable` (siempre) |
| Actualizar | editar + reiniciar contenedor | `deploy_prod.sh` |

## Checklist de primer despliegue (una sola vez)

1. Clonar el repo en el servidor y `git checkout stable`.
2. `cp .env.prod.example .env` y rellenar **todos** los valores reales.
3. (Solo si se usará sesión) generar `state.json` nativo del servidor y poner `WORKANA_USE_SESSION=true`.
4. Copiar `browser_data/` si aplica.
5. `./scripts/devops/check_prod.sh` → debe dar ✅.
6. `./scripts/devops/deploy_prod.sh`.
