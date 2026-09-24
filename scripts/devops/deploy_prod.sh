#!/usr/bin/env bash
# =============================================================================
# deploy_prod.sh — Despliegue de PRODUCCION (servidor Ubuntu)
# =============================================================================
#
# Modelo: el servidor SIEMPRE corre la rama `stable`.
#   1. Guarda el commit actual (para rollback automático).
#   2. `git fetch` + fast-forward a `origin/stable`.
#   3. `docker compose -f docker-compose.prod.yml up -d --build`.
#   4. Healthcheck; si falla -> rollback al commit previo y rebuild.
#
# NO especificas rama: siempre `stable`.
#
# Uso:
#   ./scripts/devops/deploy_prod.sh              # deploy normal
#   ./scripts/devops/deploy_prod.sh --no-build   # sin rebuild (solo recrear)
#   ./scripts/devops/deploy_prod.sh --dry-run    # muestra pasos, no ejecuta
#
# Seguridad:
#   * Aborta si no estás en `stable` o hay cambios sin commitear.
#   * Nunca usa `down -v` (no borra volumenes/datos).
#   * Rollback automático si el healthcheck falla.
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT/docker-compose.prod.yml"
COMPOSE=(docker compose -f "$COMPOSE_FILE")

# Override de sesion: se activa si .env pide WORKANA_USE_SESSION=true.
# Se resuelve tras el preflight (necesita leer .env).
SESSION_OVERRIDE="$ROOT/docker-compose.prod.session.yml"
USE_SESSION="$(grep -E '^WORKANA_USE_SESSION=' "$ROOT/.env" 2>/dev/null | cut -d= -f2 | tr -d ' ' || echo false)"
if [[ "$USE_SESSION" == "true" && -f "$SESSION_OVERRIDE" ]]; then
  COMPOSE=(docker compose -f "$COMPOSE_FILE" -f "$SESSION_OVERRIDE")
  echo "ℹ️  WORKANA_USE_SESSION=true -> se montara state.json (override de sesion)."
fi

DRY_RUN=false
NO_BUILD=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --no-build) NO_BUILD=true ;;
    *) echo "Arg desconocido: $arg"; exit 1 ;;
  esac
done

run() {
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "   [dry-run] $*"
  else
    eval "$@"
  fi
}

echo "=== Deploy PROD (Workana-Bot) ==="
echo "Repo: $ROOT"
echo "Modo: $([[ "$DRY_RUN" == "true" ]] && echo DRY-RUN || echo APPLY)"
echo

# --- Preflight ---------------------------------------------------------------
echo "[0] Preflight..."
"$ROOT/scripts/devops/check_prod.sh" || { echo "❌ Preflight falló. Abortando."; exit 1; }
echo

# --- Guardas de git ----------------------------------------------------------
BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "stable" ]]; then
  echo "❌ Estás en '$BRANCH'. Produccion exige 'stable'. Abortando."
  exit 1
fi
if ! git -C "$ROOT" diff --quiet || ! git -C "$ROOT" diff --cached --quiet; then
  echo "❌ Hay cambios sin commitear en el clon de prod. Abortando (evita perder trabajo)."
  exit 1
fi

PREV_COMMIT="$(git -C "$ROOT" rev-parse HEAD)"
echo "Commit actual (previo): $PREV_COMMIT"
echo

# --- 1) Traer stable ---------------------------------------------------------
echo "[1] git fetch + fast-forward a origin/stable..."
run "git -C '$ROOT' fetch origin stable"
run "git -C '$ROOT' merge --ff-only origin/stable"
echo

# --- 2) Build + up -----------------------------------------------------------
echo "[2] docker compose build + up..."
if [[ "$NO_BUILD" == "true" ]]; then
  run "${COMPOSE[*]} up -d"
else
  run "${COMPOSE[*]} build"
  run "${COMPOSE[*]} up -d"
fi
echo

# --- 3) Healthcheck ----------------------------------------------------------
echo "[3] Healthcheck..."
if [[ "$DRY_RUN" == "true" ]]; then
  echo "   [dry-run] se omite healthcheck"
  echo "✅ Dry-run completado (nada ejecutado)."
  exit 0
fi

sleep 10
FAILED=0
for c in workana_bot workana_api; do
  STATE="$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo 'missing')"
  if [[ "$STATE" == "running" ]]; then
    echo "  ✅ $c: running"
  else
    echo "  ❌ $c: $STATE"
    FAILED=1
  fi
done
echo

# --- 4) Rollback si falla ----------------------------------------------------
if [[ "$FAILED" -ne 0 ]]; then
  echo "❌ Healthcheck FALLÓ. Iniciando ROLLBACK al commit $PREV_COMMIT..."
  git -C "$ROOT" checkout --detach "$PREV_COMMIT"
  "${COMPOSE[@]}" build
  "${COMPOSE[@]}" up -d
  git -C "$ROOT" checkout stable
  echo "⛔ Deploy revertido. Revisa los logs: docker compose -f docker-compose.prod.yml logs --tail=100"
  exit 1
fi

echo "✅ DEPLOY OK — produccion corriendo en $(git -C "$ROOT" rev-parse --short HEAD) (stable)."
echo "   Logs: docker compose -f docker-compose.prod.yml logs -f --tail=50"
