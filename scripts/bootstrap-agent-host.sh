#!/usr/bin/env bash
# Reproduce the homelab agent setup (Claude Code + Codex) on ANY machine:
# workstation, laptop, VM. Idempotent: safe to re-run after every git pull.
#
#   npm run agents:bootstrap              # from the dotfiles checkout
#   VAULT_ADDR=http://<vault>:8200 npm run agents:bootstrap   # also pull tokens from Vault
#
# What it does, in order:
#   1. checks prerequisites (claude, node/npm, python3, jq, git, curl)
#   2. npm install (pinned rulesync)
#   3. Claude Code plugins + marketplaces          (plugins/restore.sh)
#   4. graft CLI (code-nav MCP server)             (npm, ~/.local)
#   5. jev-gate hooks                              (jev/install.sh)
#   6. instructions, MCP, settings, hooks, rules   (npm run agents:sync)
#   7. secrets: cellarette edge token + Jev key, from Vault when reachable,
#      otherwise prints the one command to run. Never prints a secret.
#   8. verifies the cellarette MCP endpoint answers and agents:check is clean.
#
# Off-LAN hosts reach the homelab MCP tools through the public edge
# (HTTPS + Bearer, see .rulesync/mcp.jsonc); lw-main uses its local :8788.
set -euo pipefail
cd "$(dirname "$0")/.."

GRAFT_VERSION="0.10.1"
LOCAL_BIN="$HOME/.local/bin"
CELLARETTE_TOKEN="${XDG_CONFIG_HOME:-$HOME/.config}/cellarette/token"
JEV_KEY="$HOME/.config/jev/api_key"
todo=()

step() { printf '\n== %s ==\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

step "platform"
# Linux and macOS only. On Windows the supported path is WSL2: Claude Code,
# node and python3 must be installed INSIDE the distro, and Claude Code is
# then started from the WSL shell. Native Windows (Git Bash / MSYS) cannot
# provide the ~/.local/bin symlinks, bash hooks and headersHelper this needs.
case "$(uname -s)" in
  Linux|Darwin) ;;
  MINGW*|MSYS*|CYGWIN*)
    echo "native Windows shell detected: run this inside WSL2 instead (see README, 'Windows')." >&2
    exit 1 ;;
  *) echo "unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac
wsl=0
grep -qi microsoft /proc/version 2>/dev/null && wsl=1
echo "  os: $(uname -s)$( ((wsl)) && echo ' (WSL)')"

step "prerequisites"
missing=()
for cmd in claude node npm python3 jq git curl; do
  have "$cmd" || { missing+=("$cmd"); continue; }
  # WSL appends the Windows PATH; a /mnt/<drive> hit is a Windows binary
  # (claude.exe, npm.cmd, the Store python3 stub) and would configure Windows
  # paths from inside Linux. Install a Linux copy in the distro instead.
  if ((wsl)) && [[ "$(command -v "$cmd")" == /mnt/* ]]; then
    missing+=("$cmd (found only the Windows one: $(command -v "$cmd"))")
  fi
done
if ((${#missing[@]})); then
  echo "missing required tools: ${missing[*]}" >&2
  echo "install them (Claude Code: https://docs.claude.com/claude-code), then re-run." >&2
  exit 1
fi
for cmd in codex rtk jcodemunch-mcp; do
  have "$cmd" && echo "  $cmd: present" || echo "  $cmd: absent (optional)"
done
have rtk || todo+=("install rtk (RTK hook is a no-op without it): https://github.com/rtk-ai/rtk")
case ":$PATH:" in
  *":$LOCAL_BIN:"*) ;;
  *) export PATH="$LOCAL_BIN:$PATH"
     todo+=("add ~/.local/bin to PATH in your shell rc (helpers + graft live there)") ;;
esac

step "npm install"
npm install --no-fund --no-audit

step "Claude Code plugins"
bash plugins/restore.sh

step "graft $GRAFT_VERSION"
if [ "$(graft --version 2>/dev/null | head -1)" != "$GRAFT_VERSION" ]; then
  npm install -g --prefix "$HOME/.local" --no-fund --no-audit "@nanonets/graft@$GRAFT_VERSION" >/dev/null
fi
echo "graft: $(graft --version 2>/dev/null | head -1)"

step "jev-gate"
bash jev/install.sh

step "agents:sync"
npm run --silent agents:sync

step "secrets"
vault_ready() { [ -n "${VAULT_ADDR:-}" ] && { [ -n "${VAULT_TOKEN:-}" ] || [ -r "${VAULT_TOKEN_FILE:-$HOME/.vault-token}" ]; }; }
url="$(python3 scripts/claude-home.py url)"
if [[ "$url" != https://* ]]; then
  echo "cellarette: local aggregator ($url), no token needed"
elif [ -s "$CELLARETTE_TOKEN" ] || [ -n "${CELLARETTE_MCP_TOKEN:-}" ]; then
  echo "cellarette: token present"
elif vault_ready; then
  cellarette-token-sync
else
  todo+=("cellarette token: VAULT_ADDR=http://<vault>:8200 cellarette-token-sync   (or: cellarette-token-sync --stdin)")
fi
if [ -s "$JEV_KEY" ] || [ -n "${TYPESAFE_API_KEY:-}" ]; then
  echo "jev: key present"
elif vault_ready; then
  jev-key-sync
else
  todo+=("jev key: VAULT_ADDR=http://<vault>:8200 jev-key-sync")
fi
# This script runs in a non-interactive shell that never sources the rc files,
# so an unset variable here does not mean the user's shells lack it.
if have codex && [[ "$url" == https://* ]] && [ -z "${CELLARETTE_MCP_TOKEN:-}" ] \
   && ! grep -qs 'CELLARETTE_MCP_TOKEN' ~/.bashrc ~/.zshrc ~/.profile ~/.zprofile ~/.bash_profile; then
  todo+=("Codex reads the edge token from the env; add to your shell rc:
      [ -r ~/.config/cellarette/token ] && export CELLARETTE_MCP_TOKEN=\"\$(<~/.config/cellarette/token)\"")
fi

step "verify"
# MCP initialize through the same headersHelper Claude Code uses; headers go
# to curl on stdin, never to the terminal.
init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"bootstrap","version":"0"}}}'
if headers="$(CLAUDE_CODE_MCP_SERVER_URL="$url" cellarette-headers 2>/dev/null)"; then
  code="$(jq -r 'to_entries[] | "\(.key): \(.value)"' <<<"$headers" \
    | curl -s -o /dev/null -w '%{http_code}' --max-time 15 -X POST "$url" \
        -H @- -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
        --data "$init" || true)"
  echo "cellarette MCP: HTTP $code ($url)"
  [ "$code" = 200 ] || todo+=("cellarette MCP answered HTTP $code: check the token / network")
else
  echo "cellarette MCP: skipped (no token yet)"
fi
npm run --silent agents:check || todo+=("agents:check reported drift (see above)")

step "done"
if ((${#todo[@]})); then
  echo "left to do:"
  printf '  - %s\n' "${todo[@]}"
else
  echo "all set. Start 'claude' in a trusted dir; accept the MCP servers when asked."
fi
