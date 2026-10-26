#!/usr/bin/env bash
# Set up the isolated WSL account `agent-ds` for a third-party (DeepSeek) agent harness.
# Run on the laptop as your normal sudo user, with the WireGuard tunnel up:
#   bash scripts/setup-agent-ds.sh
# Idempotent: safe to re-run. Secrets go straight from Vault (via lw-main) into
# agent-ds files and are never printed.
#
# What agent-ds gets: Claude Code pointed at the homelab LiteLLM (DeepSeek-only key,
# $5/30d cap), the read-only cellarette profile token `deepseek-ro`, and
# bypassPermissions. What it does NOT get: sudo, your ~/.ssh, ~/.kube, or the full
# cellarette token.
set -euo pipefail

LW="${AGENT_DS_LW:-kamil-rybacki@192.168.0.111}"
AGENT="agent-ds"
AH="/home/${AGENT}"
LITELLM_URL="${AGENT_DS_LITELLM_URL:-http://192.168.0.60:30400}"
MCP_URL="${AGENT_DS_MCP_URL:-https://cellarette-mcp.kamilandrzejrybacki.dpdns.org/mcp}"
MODEL="deepseek/deepseek-chat"

step() { printf '\n== %s ==\n' "$*"; }
die() { echo "ERROR: $*" >&2; exit 1; }
as_agent() { sudo -u "$AGENT" -H bash -c "$1"; }

vault_get() { # path field -> stdout (secret, never echoed by this script)
  ssh -o BatchMode=yes "$LW" "VAULT_ADDR=http://127.0.0.1:8200 ~/.local/bin/vault kv get -field=$2 $1"
}

write_secret() { # path field dest
  vault_get "$1" "$2" | tr -d '[:space:]' | sudo -u "$AGENT" -H sh -c "umask 077; cat > '$3'"
  sudo test -s "$3" || die "empty secret written to $3 (Vault $1#$2)"
  echo "wrote $3 ($(sudo stat -c %s "$3") bytes)"
}

step "preflight"
[[ "$(id -u)" -ne 0 ]] || die "run as your normal user, not root"
sudo -v
command -v jq >/dev/null || sudo apt-get install -y jq
command -v curl >/dev/null || sudo apt-get install -y curl
ssh -o BatchMode=yes -o ConnectTimeout=8 "$LW" true || die "cannot ssh to lw-main; is the WireGuard tunnel up?"
curl -fsS -m8 "${LITELLM_URL}/health/liveliness" >/dev/null || die "LiteLLM unreachable at ${LITELLM_URL}"
echo "tunnel, ssh and LiteLLM ok"

step "account ${AGENT} (no sudo)"
if ! id "$AGENT" >/dev/null 2>&1; then
  sudo adduser --disabled-password --gecos "" "$AGENT"
fi
if id -nG "$AGENT" | tr ' ' '\n' | grep -qxE 'sudo|admin|docker'; then
  die "${AGENT} is in a privileged group; remove it first"
fi
sudo chmod 750 "$HOME"
echo "${AGENT} exists, unprivileged; ${HOME} is 750"

step "secrets"
sudo -u "$AGENT" -H mkdir -p "$AH/.config/litellm" "$AH/.config/cellarette" "$AH/.claude" "$AH/work"
write_secret secret/homelab/litellm/laptop-agent-ds api_key "$AH/.config/litellm/key"
write_secret secret/homelab/cellarette/deepseek token "$AH/.config/cellarette/deepseek-token"
rm -f "$HOME/.config/cellarette/deepseek-token"

step "shell environment"
# The rc block only references the key file via $(<...); the secret itself is never written into ~/.bashrc.
# shellcheck disable=SC2016
as_agent '
rc=~/.bashrc
tmp=$(mktemp)
# drop any previous managed block and earlier hand-added lines, then re-add one block
sed "/^# >>> agent-ds managed >>>/,/^# <<< agent-ds managed <<</d" "$rc" \
  | grep -vE "ANTHROPIC_(BASE_URL|AUTH_TOKEN|MODEL|DEFAULT_HAIKU_MODEL)|CLAUDE_CODE_(AUTO_COMPACT_WINDOW|MAX_OUTPUT_TOKENS|DISABLE_EXPERIMENTAL_BETAS|DISABLE_NONESSENTIAL_TRAFFIC)|Claude Code -> homelab LiteLLM|DeepSeek behind LiteLLM|keep Anthropic-only beta" > "$tmp" || true
cat >> "$tmp" <<EOF
# >>> agent-ds managed >>>
export PATH="\$HOME/.local/bin:\$PATH"
# Claude Code -> homelab LiteLLM -> DeepSeek only (capped key, no Anthropic account)
export ANTHROPIC_BASE_URL='"$LITELLM_URL"'
export ANTHROPIC_AUTH_TOKEN="\$(<~/.config/litellm/key)"
export ANTHROPIC_MODEL='"$MODEL"'
export ANTHROPIC_DEFAULT_HAIKU_MODEL='"$MODEL"'
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
# DeepSeek window is smaller than the assumed 200k; keep Anthropic-only betas out
export CLAUDE_CODE_AUTO_COMPACT_WINDOW=100000
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=8000
export CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1
# <<< agent-ds managed <<<
EOF
mv "$tmp" "$rc"
'
echo "${AGENT} .bashrc managed block written"

step "Claude Code"
# shellcheck disable=SC2016
as_agent 'export PATH="$HOME/.local/bin:$PATH"; command -v claude >/dev/null || curl -fsSL https://claude.ai/install.sh | bash'
# shellcheck disable=SC2016
as_agent 'export PATH="$HOME/.local/bin:$PATH"; claude --version'

step "settings: bypassPermissions"
# Claude Code rewrites settings.json on first start; jq merges only the mode, keeping the rest.
# shellcheck disable=SC2016
as_agent '
f=~/.claude/settings.json
[ -s "$f" ] || echo "{}" > "$f"
jq ".permissions.defaultMode = \"bypassPermissions\"" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
cat "$f"
'

step "MCP: cellarette (deepseek-ro)"
# shellcheck disable=SC2016
as_agent '
export PATH="$HOME/.local/bin:$PATH"
claude mcp remove -s user cellarette >/dev/null 2>&1 || true
claude mcp add -s user --transport http cellarette '"$MCP_URL"' \
  --header "Authorization: Bearer $(<~/.config/cellarette/deepseek-token)" >/dev/null
echo "cellarette MCP registered"
'

step "verify"
# shellcheck disable=SC2016
as_agent '
k=$(<~/.config/litellm/key)
r=$(curl -s -m60 '"$LITELLM_URL"'/v1/messages -H "x-api-key: $k" -H "anthropic-version: 2023-06-01" -H "Content-Type: application/json" \
  -d "{\"model\":\"'"$MODEL"'\",\"max_tokens\":10,\"messages\":[{\"role\":\"user\",\"content\":\"reply with: ok\"}]}")
echo "LiteLLM (DeepSeek): $(jq -r ".content[0].text // .error.message" <<<"$r")"
t=$(<~/.config/cellarette/deepseek-token)
n=$(curl -s -m20 -X POST '"$MCP_URL"' -H "Authorization: Bearer $t" -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}" \
  | sed -n "s/^data: //p" | jq ".result.tools | length")
echo "cellarette deepseek-ro tools: $n (expected 35)"
'

step "done"
cat <<EOF
Start it:
  sudo -iu ${AGENT}
  cd ~/work && claude
First start asks once to confirm bypass-permissions mode. Then /mcp shows cellarette.
EOF
