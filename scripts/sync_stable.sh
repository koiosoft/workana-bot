#!/usr/bin/env bash
set -euo pipefail

echo "🔄 Syncing 'stable' with latest 'main' (without changing working branch)..."

HAS_REMOTE=false
if git remote get-url origin >/dev/null 2>&1; then
  HAS_REMOTE=true
fi

# 1. Traer la foto exacta de origin
if [[ "$HAS_REMOTE" == "true" ]]; then
  echo "📥 Fetching latest state from origin..."
  git fetch origin main:main stable:stable 2>/dev/null || git fetch origin --prune
fi

# 2. Asegurar que 'stable' exista localmente
if ! git rev-parse --verify stable >/dev/null 2>&1; then
  echo "ℹ️ Creating local 'stable' branch from 'main'..."
  git branch stable main
fi

# 2b. Si 'stable' está activa en un worktree (p. ej. el de build, tras un build
#     interrumpido o a medio correr), git no permite que `git branch -f` / `fetch .`
#     la muevan. sync_stable no fuerza por sí mismo: AVISA y pregunta al humano.
#     YES -> fuerza la liberación (deja ese worktree en detached origin/stable).
#     NO  -> termina EL PROCESO sin modificar nada (el humano resuelve aparte).
BUILD_WT=$(git worktree list --porcelain | awk '/^worktree /{wt=$2} /^branch refs\/heads\/stable/{print wt; exit}')
if [ -n "$BUILD_WT" ]; then
  echo ""
  echo "⚠️  'stable' está ACTIVA en un worktree de build:"
  echo "      $BUILD_WT"
  echo "   Mientras siga así, git no permite sincronizar 'stable'."
  if ! git -C "$BUILD_WT" diff --quiet || ! git -C "$BUILD_WT" diff --cached --quiet; then
    echo ""
    echo "   ⚠️  Ojo: ese worktree tiene cambios SIN COMMITEAR."
    echo "       Forzar la limpieza DESCARTARÁ esos cambios."
  fi
  echo ""
  echo "   Opción YES:  fuerza limpiar ese worktree -> lo deja en detached (origin/stable)."
  echo "   Opción NO :  termina este proceso sin tocar nada."
  echo ""
  printf -- "   ¿Desea forzar limpiar el worktree de build? (YES/NO): " >&2
  _ans=""
  if [ -t 0 ]; then
    read -r _ans || true
  fi
  case "${_ans:-}" in
    [yY]|[yY][eE][sS])
      echo "🔓 Forzando limpieza del worktree de build..."
      git -C "$BUILD_WT" fetch origin stable -q 2>/dev/null || true
      git -C "$BUILD_WT" checkout -f --detach origin/stable
      echo "   ✅ '$BUILD_WT' movido a detached (origin/stable). 'stable' liberada."
      ;;
    *)
      echo "   Terminado sin modificar. 'stable' sigue a cargo del worktree de build." >&2
      echo "   Puedes liberarla después con: ./fastlane/build.sh cleanup" >&2
      exit 0
      ;;
  esac
fi

# 3. Sincronizar 'stable' con 'main'. Se usa `git update-ref` (plumbing) + `merge-base`,
#    que a diferencia de `git branch -f` / `git fetch . main:stable` no se bloquea aunque
#    'stable' esté checkeada en algún worktree. Cubre fast-forward; si hay divergencia
#    real (stable adelantó algo que main no tiene), detiene pidiendo resolución manual.
echo "🔀 Sincronizando 'stable' con 'main'..."
if git merge-base --is-ancestor stable main 2>/dev/null; then
  # Fast-forward posible: mover la ref hacia main sin tocar working trees.
  NEW_STABLE="$(git rev-parse main)"
  CUR_STABLE="$(git rev-parse stable)"
  if [ "$NEW_STABLE" != "$CUR_STABLE" ]; then
    git update-ref refs/heads/stable "$NEW_STABLE" "$CUR_STABLE"
    echo "   ✅ 'stable' fast-forwarded a main ($(git rev-parse --short main))."
  else
    echo "   ℹ️  'stable' ya está en el mismo commit que main."
  fi
else
  echo "--------------------------------------------------------" >&2
  echo "❌ 'stable' y 'main' divergieron." >&2
  echo "   (Este script solo cubre fast-forward; resuelve el merge manualmente.)" >&2
  echo "   Commits en 'stable' que 'main' no tiene:" >&2
  git log --oneline main..stable >&2 || true
  echo "--------------------------------------------------------" >&2
  exit 1
fi

# 4. Si hay remoto, subir 'stable'
if [[ "$HAS_REMOTE" == "true" ]]; then
  echo "📤 Pushing updated 'stable' to origin..."
  if ! git push origin stable; then
    echo "❌ Error: Failed to push 'stable' to origin."
    exit 1
  fi
fi

echo "✅ 'stable' is now synchronized with 'main' and pushed to remote (your current branch was untouched!)."
