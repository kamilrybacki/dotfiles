#!/usr/bin/env bash
# Regenerate every agent's instruction file from the single source of truth
# (.rulesync/rules/*.md) using rulesync. Edit the shared blocks ONCE there and
# run this; every agent gets its native file. See .rulesync/AGENTS-SYNC.md.
#
# delete:false in rulesync.jsonc guarantees the hand-maintained ~/.claude/rules/
# tree (Claude-only language rules) is never pruned.
set -euo pipefail
cd "$(dirname "$0")/.."   # dotfiles root (holds .rulesync/ + rulesync.jsonc)

RS=./node_modules/.bin/rulesync
[ -x "$RS" ] || { echo "rulesync not installed — run: npm install" >&2; exit 1; }

HELM_REPO="${HELM_REPO:-$HOME/Code/helm}"
HERMES_FILE="$HELM_REPO/charts/hermes/files/AGENTS.md"

# Local agents → their live global paths.
"$RS" generate -g --targets claudecode --features rules
"$RS" generate --targets codexcli --features rules -o "$HOME/.codex"

# Hermes lives in a container: render to staging, copy into the helm chart.
# The actual deploy is GitOps — commit + PR the helm change; ArgoCD seeds the PVC.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
"$RS" generate --targets hermesagent --features rules -o "$STAGE"
if [ -f "$STAGE/.hermes.md" ] && [ -f "$HERMES_FILE" ]; then
  if cmp -s "$STAGE/.hermes.md" "$HERMES_FILE"; then
    echo "hermes: unchanged"
  else
    cp "$STAGE/.hermes.md" "$HERMES_FILE"
    echo "hermes: UPDATED $HERMES_FILE — commit + PR to deploy (ArgoCD → ConfigMap → PVC)"
  fi
fi
echo "agents synced."
