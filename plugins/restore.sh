#!/usr/bin/env bash
# Restore all Claude Code plugin marketplaces + plugins on a fresh machine, so a
# bare install needs only: this dotfiles sync + a reachable Cellarette.
# Source of truth: marketplaces.txt (name<TAB>repo) and plugins.txt (name@marketplace).
# Third-party plugins stay upstream (not vendored) — this just re-adds + re-installs them.
set -euo pipefail
cd "$(dirname "$0")"

command -v claude >/dev/null || { echo "claude CLI not found" >&2; exit 1; }

echo "== marketplaces =="
while IFS=$'\t' read -r name repo; do
  [ -z "${name:-}" ] && continue
  echo "  + $name ($repo)"
  claude plugin marketplace add "$repo" 2>/dev/null || echo "    (already added or failed: $name)"
done < marketplaces.txt

echo "== plugins =="
while IFS= read -r spec; do
  [ -z "${spec:-}" ] && continue
  echo "  + $spec"
  claude plugin install "$spec" 2>/dev/null || echo "    (already installed or failed: $spec)"
done < plugins.txt

echo "done. Run 'claude plugin list' to verify."
