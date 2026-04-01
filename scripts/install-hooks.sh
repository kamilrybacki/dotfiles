#!/usr/bin/env bash
# Install git hooks for this repository.
# Run once after cloning: ./scripts/install-hooks.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

mkdir -p "$HOOKS_DIR"

cat > "$HOOKS_DIR/pre-commit" << 'EOF'
#!/usr/bin/env bash
# Pre-commit hook: block commits containing secrets or sensitive data.
# Scans staged diff for known secret patterns and sensitive filenames.

set -euo pipefail

RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

FOUND=0

# ── Part 1: Block sensitive files by name ──────────────────────────────────

FORBIDDEN_PATTERNS=(
  "homelab-credentials"
  "homelab-setup-vars"
  ".env.local"
  "id_rsa"
  "id_ed25519"
  "credentials.json"
)

for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
  matches=$(git diff --cached --name-only | grep -i "$pattern" || true)
  if [[ -n "$matches" ]]; then
    echo -e "${RED}SENSITIVE FILE:${NC} matches '$pattern':"
    echo "$matches" | sed 's/^/  /'
    FOUND=1
  fi
done

# ── Part 2: Scan diff content for secret patterns ─────────────────────────

DIFF=$(git diff --cached --diff-filter=ACMR 2>/dev/null || true)

if [ -n "$DIFF" ]; then
  SECRET_PATTERNS=(
    'nvapi-[A-Za-z0-9_-]{20,}|NVIDIA API key'
    'gsk_[A-Za-z0-9]{20,}|Groq API key'
    'sk-[a-f0-9]{32}|DeepSeek API key'
    '[0-9]{9,10}:AA[A-Za-z0-9_-]{33,36}|Telegram bot token'
    'Bearer [a-f0-9]{64}|Bearer token (64-char hex)'
    'PRIVATE KEY|Private key block'
    'hvs\.[A-Za-z0-9]{20,}|Vault token'
    'api\.telegram\.org/bot[0-9]|Telegram API URL with token'
    'ansible_become_pass\s*[=:]\s*\S{8,}|Ansible become password'
    'ssh_pass\w*\s*[=:]\s*\S{8,}|SSH password'
    'AKIA[0-9A-Z]{16}|AWS access key'
    'ghp_[A-Za-z0-9]{36}|GitHub personal access token'
    'glpat-[A-Za-z0-9_-]{20}|GitLab personal access token'
  )

  for entry in "${SECRET_PATTERNS[@]}"; do
    PATTERN="${entry%%|*}"
    LABEL="${entry#*|}"

    MATCHES=$(echo "$DIFF" | grep -nP "^\+" | grep -P "$PATTERN" || true)
    if [ -n "$MATCHES" ]; then
      echo -e "${RED}SECRET DETECTED:${NC} $LABEL"
      echo "$MATCHES" | head -3
      echo ""
      FOUND=1
    fi
  done
fi

# ── Verdict ────────────────────────────────────────────────────────────────

if [ "$FOUND" -ne 0 ]; then
  echo -e "${RED}COMMIT BLOCKED:${NC} Remove secrets/sensitive files before committing."
  echo "Use Vault references or \$env variables instead of hardcoded values."
  echo -e "${YELLOW}To bypass (emergency only):${NC} git commit --no-verify"
  exit 1
fi

exit 0
EOF

  chmod +x "$HOOKS_DIR/pre-commit"
  echo "Hooks installed for $(basename "$REPO_ROOT")"
