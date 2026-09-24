#!/usr/bin/env bash
# =============================================================================
# rollback_prod.sh — Revertir produccion a un commit anterior de `stable`
# =============================================================================
#
# Uso:
#   ./scripts/devops/rollback_prod.sh                # vuelve al commit anterior
#   ./scripts/devops/rollback_prod.sh <commit|tag>   # vuelve a uno especifico
#
# No borra datos: solo re-construye la imagen desde el commit elegido.
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/docker-compose.prod.yml")

TARGET="${1:-HEAD~1}"

if ! git -C "$ROOT" rev-parse --verify "$TARGET" >/dev/null 2>&1; then
  echo "❌ Referencia inválida: $TARGET"
  exit 1
fi

echo "=== ROLLBACK PROD ==="
echo "Repo  : $ROOT"
echo "Actual: $(git -C "$ROOT" rev-parse --short HEAD)"
echo "Destino: $(git -C "$ROOT" rev-parse --short "$TARGET")"
echo

echo "[1] git fetch (para asegurar refs)..."
git -C "$ROOT" fetch origin stable || true

echo "[2] Checkout detached en $TARGET..."
git -C "$ROOT" checkout --detach "$TARGET"

echo "[3] Rebuild + up..."
"${COMPOSE[@]}" build
"${COMPOSE[@]}" up -d

echo "[4] Verificación..."
sleep 8
for c in workana_bot workana_api; do
  STATE="$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo missing)"
  echo "   $c: $STATE"
done

echo
echo "✅ Rollback aplicado en $(git -C "$ROOT" rev-parse --short HEAD)."
echo "   NOTA: el clon queda en detached HEAD. Para volver a 'stable':"
echo "     git -C '$ROOT' checkout stable"
