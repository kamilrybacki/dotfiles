#!/usr/bin/env bash
# run-reviews.sh - Reviewer A (Codex, read-only) and optional Reviewer B
# (OpenCode agent "reviewer", Kimi K3 on OpenCode Go), run in parallel. Writes outputs to a dir.
#
# Usage: run-reviews.sh --repo DIR --base REF --codex-model M --codex-effort E
#          --reviewer-b yes|no [--rank N] [--scope TEXT] [--out DIR] [--only both|codex|reviewer-b] [--dry-run]
#
# Reviewer B is refused whenever the exact outgoing prompt classifies as restricted
# (sensitivity.py, deterministic rules), regardless of --reviewer-b. The prompt is rebuilt
# and re-classified right before every Reviewer B call.
#
# Exit: 0 when at least one reviewer returned a VERDICT; 2 when none did.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$PWD"; base=""; codex_model=""; codex_effort=""; reviewer_b=no
rank=2; scope="The diff below is the complete change under review."; out=""; dry=0; only=both
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) repo="$2"; shift 2 ;;
    --base) base="$2"; shift 2 ;;
    --codex-model) codex_model="$2"; shift 2 ;;
    --codex-effort) codex_effort="$2"; shift 2 ;;
    --reviewer-b) reviewer_b="$2"; shift 2 ;;
    --rank) rank="$2"; shift 2 ;;
    --scope) scope="$2"; shift 2 ;;
    --out) out="$2"; shift 2 ;;
    --only) only="$2"; shift 2 ;;
    --dry-run) dry=1; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "run-reviews.sh: unknown argument: $1" >&2; exit 64 ;;
  esac
done
[ -n "$base" ] && [ -n "$codex_model" ] && [ -n "$codex_effort" ] \
  || { echo "run-reviews.sh: --base, --codex-model and --codex-effort are required" >&2; exit 64; }
case "$only" in both|codex|reviewer-b) ;; *) echo "run-reviews.sh: --only must be both|codex|reviewer-b" >&2; exit 64 ;; esac
[ -n "$out" ] || out="$(mktemp -d "${TMPDIR:-/tmp}/cross-review.XXXXXX")"
mkdir -p "$out"

case "$rank" in
  3) focus="Security, auth/crypto, secrets handling, infra/CI, migrations and public contracts. Assume an attacker controls any untrusted input the diff parses. Secrets must never be logged, printed or committed." ;;
  *) focus="Correctness bugs, regressions, error handling, and unsafe shell or file operations." ;;
esac

# Builds diff.patch and the outgoing prompt.md from the current committed range.
build_payload() {
  git -C "$repo" diff "$base...HEAD" > "$out/diff.patch"
  [ -s "$out/diff.patch" ] || { echo "run-reviews.sh: empty diff for $base...HEAD" >&2; exit 66; }
  python3 - "$here/review-prompt.md" "$out/diff.patch" "$out/prompt.md" "$base" "$scope" "$focus" <<'PY'
import sys
tpl, diff, dst, base, scope, focus = sys.argv[1:7]
t = open(tpl).read()
t = (t.replace("{{SCOPE}}", scope).replace("{{FOCUS}}", focus)
      .replace("{{BASE}}", base).replace("{{DIFF}}", open(diff).read()))
open(dst, "w").write(t)
PY
}

# Classifies the exact outgoing prompt. Prints the JSON report; returns 0 always.
classify_payload() {
  python3 "$here/sensitivity.py" payload --repo "$repo" --base "$base" --text-file "$out/prompt.md" 2>/dev/null \
    || echo '{"tier": "restricted", "reasons": ["sensitivity.py failed: refusing"]}'
}

build_payload
classify_payload > "$out/payload.json"

run_codex() {
  if [ "$only" != both ] && [ "$only" != codex ]; then
    echo "SKIPPED: not requested (--only $only)" > "$out/codex.status"; return 0
  fi
  if ! command -v codex >/dev/null 2>&1; then
    echo "SKIPPED: codex not installed (Reviewer A skipped)" > "$out/codex.status"; return 0
  fi
  local cmd=(codex exec -m "$codex_model" -c "model_reasoning_effort=\"$codex_effort\""
             -s read-only -C "$repo" -o "$out/codex.md" -)
  if [ "$dry" -eq 1 ]; then echo "DRY: ${cmd[*]} < $out/prompt.md" > "$out/codex.status"; return 0; fi
  if timeout 1500 "${cmd[@]}" < "$out/prompt.md" > "$out/codex.log" 2>&1 && [ -s "$out/codex.md" ]; then
    echo "RAN" > "$out/codex.status"
  else
    echo "FAILED: codex exited non-zero or wrote no output (see codex.log)" > "$out/codex.status"
  fi
}

run_reviewer_b() {
  if [ "$only" != both ] && [ "$only" != reviewer-b ]; then
    echo "SKIPPED: not requested (--only $only)" > "$out/reviewer-b.status"; return 0
  fi
  # Re-build and re-classify the exact payload right before this call, every round.
  build_payload
  local tier
  tier="$(classify_payload | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("tier","restricted"))
except Exception: print("restricted")')"
  if [ "$tier" != standard ]; then
    echo "REFUSED: outgoing payload is $tier (deterministic rules). Reviewer B never receives restricted data." > "$out/reviewer-b.status"
    return 0
  fi
  if [ "$reviewer_b" != yes ]; then
    echo "SKIPPED: rank $rank rule (Reviewer B off)" > "$out/reviewer-b.status"; return 0
  fi
  if ! command -v opencode >/dev/null 2>&1; then
    echo "SKIPPED: opencode not installed (Reviewer B skipped)" > "$out/reviewer-b.status"; return 0
  fi
  if ! opencode agent list 2>/dev/null | grep -qE '(^|[[:space:]])reviewer([[:space:]]|$)'; then
    echo "SKIPPED: opencode agent 'reviewer' missing (run npm run agents:sync)" > "$out/reviewer-b.status"; return 0
  fi
  local cmd=(opencode run --agent reviewer --dir "$repo"
             "Review the attached diff exactly as the attached instructions say." -f "$out/prompt.md")
  if [ "$dry" -eq 1 ]; then echo "DRY: ${cmd[*]}" > "$out/reviewer-b.status"; return 0; fi
  if timeout 1500 "${cmd[@]}" > "$out/reviewer-b.md" 2> "$out/reviewer-b.log" && [ -s "$out/reviewer-b.md" ]; then
    echo "RAN" > "$out/reviewer-b.status"
  else
    echo "FAILED: opencode exited non-zero or wrote no output (see reviewer-b.log)" > "$out/reviewer-b.status"
  fi
}

run_codex & pa=$!
run_reviewer_b & pb=$!
wait "$pa" || true
wait "$pb" || true

verdict_of() {
  local f="$1"
  [ -s "$f" ] || { echo "NO_OUTPUT"; return; }
  grep -E '^VERDICT: (APPROVE|CHANGES_REQUESTED)$' "$f" | tail -1 | sed 's/^VERDICT: //' | grep . || echo "NO_VERDICT"
}
ran=0
echo "payload: $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["tier"])' "$out/payload.json")"
for pair in "codex:codex.md:codex.status" "reviewer-b:reviewer-b.md:reviewer-b.status"; do
  IFS=: read -r name md st <<<"$pair"
  status="$(cat "$out/$st")"
  if [ "$dry" -eq 1 ]; then echo "$name: $status"; continue; fi
  case "$status" in
    RAN) v="$(verdict_of "$out/$md")"; echo "$name: VERDICT=$v"; [ "$v" = NO_VERDICT ] || ran=$((ran + 1)) ;;
    *) echo "$name: $status" ;;
  esac
done
echo "out: $out"
if [ "$dry" -eq 1 ]; then exit 0; fi
if [ "$ran" -eq 0 ]; then
  echo "NO REVIEWER PRODUCED A VERDICT. Cross-review did not happen." >&2
  exit 2
fi
