#!/usr/bin/env bash
# =============================================================================
# check_prod.sh — Preflight de produccion (SOLO LEE, no modifica nada)
# =============================================================================
#
# Verifica que el servidor tiene TODO lo necesario ANTES de desplegar.
# Es el paso obligatorio previo a deploy_prod.sh (dry-run). No arranca nada.
#
# Uso:
#   ./scripts/devops/check_prod.sh
#
# Salida: lista de chequeos OK/FALLO y exit code 0 (todo ok) o 1 (algo falta).
# =============================================================================
set -uo pipefail

FAIL=0
ok()   { echo "  ✅ $1"; }
fail() { echo "  ❌ $1"; FAIL=1; }
warn() { echo "  ⚠️  $1"; }

echo "=== Preflight de PRODUCCION (Workana-Bot) ==="
echo

# 0) Raiz del repo (este script vive en scripts/devops/)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "Repo: $ROOT"
echo

# 1) Rama actual
CURRENT_BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
echo "[1] Rama actual"
if [[ "$CURRENT_BRANCH" == "stable" ]]; then
  ok "estás en 'stable'"
else
  warn "estás en '$CURRENT_BRANCH' (produccion exige 'stable')"
fi
echo

# 2) Docker + compose
echo "[2] Docker"
if command -v docker >/dev/null 2>&1; then ok "docker instalado"; else fail "docker NO encontrado"; fi
if docker compose version >/dev/null 2>&1; then ok "docker compose (plugin) disponible"; else fail "docker compose NO disponible"; fi
if docker info >/dev/null 2>&1; then ok "daemon docker accesible"; else fail "daemon docker NO accesible (permisos?)"; fi
echo

# 3) Compose de produccion
echo "[3] Manifiesto de produccion"
if [[ -f "$ROOT/docker-compose.prod.yml" ]]; then
  ok "docker-compose.prod.yml presente"
  if docker compose -f "$ROOT/docker-compose.prod.yml" config >/dev/null 2>&1; then
    ok "compose valido (config parsea)"
  else
    fail "compose invalido (revisa sintaxis/variables)"
  fi
else
  fail "docker-compose.prod.yml NO existe"
fi
echo

# 4) Archivos .env (NO deben estar en git; deben existir en el servidor)
echo "[4] Variables de entorno (.env)"
if [[ -f "$ROOT/.env" ]]; then
  ok ".env presente"
  # Chequeo de variables minimas (solo presencia, nunca mostramos valores)
  for var in SCRAPER_SOURCE TELEGRAM_BOT_TOKEN MONGO_URI MONGO_DB_NAME; do
    if grep -qE "^${var}=.+" "$ROOT/.env"; then
      ok "  ${var} definida"
    else
      fail "  ${var} FALTA o vacia en .env"
    fi
  done
  # API de IA: al menos una
  if grep -qE "^(GEMINI_API_KEY|OPENROUTER_API_KEY)=.+" "$ROOT/.env"; then
    ok "  una API key de IA definida"
  else
    fail "  falta GEMINI_API_KEY u OPENROUTER_API_KEY"
  fi
  # Backend de BD: Atlas (mongodb+srv o host remoto) vs mongodb local
  if grep -qE '^MONGO_URI=.*(mongodb\+srv|mongodb\.net)' "$ROOT/.env"; then
    ok "  MONGO_URI apunta a ATLAS (modo produccion)"
  elif grep -qE '^MONGO_URI=.*@mongodb:' "$ROOT/.env"; then
    warn "  MONGO_URI apunta al 'mongodb' local. En prod se espera Atlas; usa --profile local-db si es intencional."
  else
    warn "  no pude clasificar MONGO_URI (¿Atlas? ¿local?). Revisa manualmente."
  fi
else
  fail ".env NO existe (copia .env.prod.example -> .env y rellena)"
fi
echo

# 5) Sesion de Workana (opcional segun WORKANA_USE_SESSION)
echo "[5] Sesion de Workana (opcional)"
USE_SESSION="$(grep -E '^WORKANA_USE_SESSION=' "$ROOT/.env" 2>/dev/null | cut -d= -f2 | tr -d ' ' || echo 'false')"
if [[ "$USE_SESSION" == "true" ]]; then
  if [[ -f "$ROOT/state.json" ]]; then
    ok "WORKANA_USE_SESSION=true y state.json presente"
  else
    fail "WORKANA_USE_SESSION=true pero falta state.json en el servidor"
  fi
else
  ok "WORKANA_USE_SESSION=false (no se usa sesion; scraping publico)"
fi
if [[ -d "$ROOT/browser_data" ]]; then
  ok "browser_data/ presente"
else
  warn "browser_data/ ausente (se creará al primer arranque)"
fi
echo

# 6) Remote git accesible
echo "[6] Acceso a GitHub"
if git -C "$ROOT" remote get-url origin >/dev/null 2>&1; then
  ok "remote 'origin' configurado"
  if git -C "$ROOT" ls-remote --heads origin stable 2>/dev/null | grep -q .; then
    ok "origin accesible y tiene 'stable'"
  else
    fail "origin NO tiene rama 'stable' (o no hay acceso). Corre el release primero."
  fi
else
  fail "remote 'origin' NO configurado"
fi
echo

echo "==============================================="
if [[ "$FAIL" -eq 0 ]]; then
  echo "✅ PREFLIGHT OK — listo para ./scripts/devops/deploy_prod.sh"
  exit 0
else
  echo "❌ PREFLIGHT FALLÓ — resuelve lo anterior antes de desplegar."
  exit 1
fi
