#!/usr/bin/env bash
# Drift guard: fail (non-zero) if any agent's live file is out of sync with the
# .rulesync/ source. Use in a pre-commit hook or CI. Read-only — never writes.
set -euo pipefail
cd "$(dirname "$0")/.."

RS=./node_modules/.bin/rulesync
[ -x "$RS" ] || { echo "rulesync not installed — run: npm install" >&2; exit 1; }

HELM_REPO="${HELM_REPO:-$HOME/Code/helm}"
HERMES_FILE="$HELM_REPO/charts/hermes/files/AGENTS.md"
rc=0

"$RS" generate -g --targets claudecode --features rules --check || rc=1
"$RS" generate -g --targets claudecode --features mcp --check || rc=1
"$RS" generate --targets codexcli --features rules -o "$HOME/.codex" --check || rc=1
"$RS" generate -g --targets codexcli --features mcp --check || rc=1

# Hermes: render to staging and byte-compare against the committed helm file.
STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
"$RS" generate --targets hermesagent --features rules -o "$STAGE" >/dev/null 2>&1 || true
if [ -f "$STAGE/.hermes.md" ] && [ -f "$HERMES_FILE" ]; then
  if cmp -s "$STAGE/.hermes.md" "$HERMES_FILE"; then
    echo "ok     hermes"
  else
    echo "DRIFT  hermes: $HERMES_FILE differs from source — run npm run agents:sync"
    rc=1
  fi
fi

# Our hand-authored skills (byte-faithful copy, not rulesync-generated).
for d in skills/*/; do
  [ -d "$d" ] || continue
  b="$(basename "$d")"
  if diff -rq "$d" "$HOME/.claude/skills/$b" >/dev/null 2>&1; then :; else
    echo "DRIFT  skill: $b"; rc=1
  fi
done
[ "$rc" -eq 0 ] && echo "ok     skills"

[ "$rc" -eq 0 ] && echo "all agents in sync." || echo "drift detected — run: npm run agents:sync" >&2
exit "$rc"
