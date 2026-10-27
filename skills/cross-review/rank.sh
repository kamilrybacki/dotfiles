#!/usr/bin/env bash
# rank.sh - deterministic change rank for /cross-review.
#
# Usage: rank.sh --repo DIR --base REF [--min-rank N]
#
# Prints key=value lines (reason= repeats):
#   rank, codex_model, codex_effort, reviewer_b (yes|no), tier, files, lines, reason=...
#
# Rank 1 trivial (docs/tests only, <=150 changed lines)
# Rank 2 normal feature/bugfix (default)
# Rank 3 security/auth/crypto, infra/CI/installers, secrets, DB migrations,
#        public API/contract, dependency/lockfiles, or >400 changed lines.
# --min-rank can only RAISE the rank. Lowering is not possible by design.
set -euo pipefail

repo="$PWD"
base=""
min_rank=1
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) repo="$2"; shift 2 ;;
    --base) base="$2"; shift 2 ;;
    --min-rank) min_rank="$2"; shift 2 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "rank.sh: unknown argument: $1" >&2; exit 64 ;;
  esac
done
[ -n "$base" ] || { echo "rank.sh: --base REF is required" >&2; exit 64; }
case "$min_rank" in 1|2|3) ;; *) echo "rank.sh: --min-rank must be 1, 2 or 3" >&2; exit 64 ;; esac

g() { git -C "$repo" "$@"; }
g rev-parse --verify --quiet "$base^{commit}" >/dev/null \
  || { echo "rank.sh: unknown base ref: $base" >&2; exit 65; }

mapfile -t files < <(g diff --name-only "$base...HEAD")
[ "${#files[@]}" -gt 0 ] || { echo "rank.sh: no changes in $base...HEAD" >&2; exit 66; }

read -r ins del < <(g diff --numstat "$base...HEAD" \
  | awk '$1 != "-" { i += $1; d += $2 } END { print i + 0, d + 0 }')
lines=$((ins + del))

is_doc() { case "$1" in *.md|*.mdx|*.txt|*.rst|docs/*|*/docs/*) return 0 ;; esac; return 1; }
is_test() {
  case "$1" in
    test/*|tests/*|*/test/*|*/tests/*|*/__tests__/*|test_*|*/test_*|*_test.*|*.test.*|*.spec.*|*_spec.*) return 0 ;;
  esac
  return 1
}
# Prints the reason and returns 0 when the path forces rank 3.
r3_path() {
  case "${1,,}" in
    *auth*|*crypt*|*secret*|*vault*|*sops*|*.pem|*.key|*token*|*passw*|*rbac*|*acl*|*permission*|*polic*|*.env|*.env.*)
      echo "security path: $1"; return 0 ;;
    .github/*|.gitlab-ci*|.forgejo/*|*helm*|*charts/*|*ansible*|*argocd*|*terraform*|*.tf|*.tfvars|Dockerfile*|*/Dockerfile*|*compose*.y*ml|*k8s*|*kube*|install.sh|*/install.sh|*bootstrap*|scripts/*|*rulesync*)
      echo "infra/CI/installer: $1"; return 0 ;;
    *migrat*|*.sql|*schema.prisma|*alembic/*)
      echo "DB migration: $1"; return 0 ;;
    *openapi*|*swagger*|*.proto|*.graphql|*.gql|api/*|*/api/*|*contract*)
      echo "public API/contract: $1"; return 0 ;;
    package.json|*/package.json|*package-lock.json|*pnpm-lock.yaml|*yarn.lock|*Cargo.lock|*Cargo.toml|*go.mod|*go.sum|*requirements*.txt|*pyproject.toml|*poetry.lock|*uv.lock|*Pipfile*|*Gemfile*|*composer.lock)
      echo "dependency/lockfile: $1"; return 0 ;;
  esac
  return 1
}
secret_kw='password|passwd|secret|api[_-]?key|credential|oauth|jwt|hmac|encrypt|decrypt|crypto|bcrypt|argon2|authoriz|authenticat|sudo|privilege|drop table|alter table|truncate table|chmod|chown'

rank=1
docs_only=1
for f in "${files[@]}"; do
  if ! is_doc "$f" && ! is_test "$f"; then docs_only=0; fi
done
if [ "$docs_only" -eq 1 ] && [ "$lines" -le 150 ]; then rank=1; else rank=2; fi

reasons=()
for f in "${files[@]}"; do
  if r=$(r3_path "$f"); then rank=3; reasons+=("rank3 $r"); fi
done

for f in "${files[@]}"; do
  is_doc "$f" && continue
  hit=$(g diff "$base...HEAD" -- "$f" | grep -E '^\+[^+]' | grep -ioE "$secret_kw" | head -1 || true)
  if [ -n "$hit" ]; then rank=3; reasons+=("rank3 security keyword '$hit' in added lines: $f"); fi
done

if [ "$lines" -gt 400 ]; then rank=3; reasons+=("rank3 diff size $lines changed lines > 400"); fi
if [ "$docs_only" -eq 1 ] && [ "$rank" -eq 1 ]; then
  reasons+=("rank1 docs/tests-only, $lines changed lines <= 150")
elif [ "$rank" -eq 2 ]; then
  reasons+=("rank2 default: normal feature/bugfix")
fi

if [ "$min_rank" -gt "$rank" ]; then
  reasons+=("operator raised rank $rank -> $min_rank via --min-rank")
  rank=$min_rank
fi

# Sensitivity gate: jev-gate route. Anything other than open|standard, or a
# missing/failed jev-gate, is treated as restricted.
tier=restricted
if command -v jev-gate >/dev/null 2>&1; then
  fargs=()
  for f in "${files[@]}"; do fargs+=(--file "$f"); done
  out=$(cd "$repo" && jev-gate route --task "cross-review $base...HEAD" "${fargs[@]}" 2>/dev/null) || out=""
  tier=$(printf '%s' "$out" | python3 -c '
import json, sys
try:
    t = json.load(sys.stdin).get("tier", "")
except Exception:
    t = ""
print(t if t in ("open", "standard", "restricted") else "restricted")')
else
  reasons+=("jev-gate not on PATH: tier treated as restricted")
fi
[ "$tier" = restricted ] && reasons+=("tier=restricted: no OpenCode Go / open-model reviewer")

case "$rank" in
  1) codex_model=gpt-6-luna; codex_effort=low ;;
  2) codex_model=gpt-6-luna; codex_effort=medium ;;
  3) codex_model=gpt-6.1-sol; codex_effort=medium ;;
esac
reviewer_b=no
if [ "$rank" -ge 2 ] && [ "$tier" != restricted ]; then reviewer_b=yes; fi
if [ "$rank" -eq 1 ]; then reasons+=("rank1: Reviewer B skipped by rule"); fi

echo "rank=$rank"
echo "codex_model=$codex_model"
echo "codex_effort=$codex_effort"
echo "reviewer_b=$reviewer_b"
echo "tier=$tier"
echo "files=${#files[@]}"
echo "lines=$lines"
for r in "${reasons[@]}"; do echo "reason=$r"; done
