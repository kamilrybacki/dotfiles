#!/usr/bin/env bash
# Regenerate every agent's instruction file from the single source of truth
# (.rulesync/rules/*.md) using rulesync. Edit the shared blocks ONCE there and
# run this; every agent gets its native file. See .rulesync/AGENTS-SYNC.md.
#
# delete:false in rulesync.jsonc guarantees ~/.claude/rules/ (the vendored ECC
# rules tree, copied by scripts/claude-home.py) is never pruned.
set -euo pipefail
cd "$(dirname "$0")/.."   # dotfiles root (holds .rulesync/ + rulesync.jsonc)

RS=./node_modules/.bin/rulesync
[ -x "$RS" ] || { echo "rulesync not installed — run: npm install" >&2; exit 1; }

. scripts/lib/stage-mcp.sh

# Helpers on PATH first: splicedock-headers is the MCP headersHelper below.
bash splicedock/install.sh

# Local agents → their live global paths.
# rules: claudecode supports global; codexcli does not, so it needs -o ~/.codex.
# mcp:   both support global (-g) and MERGE into the existing config, preserving
#        all other settings (model/auth in config.toml, projects/history in
#        ~/.claude.json). Rendered per host from a staged copy (lib/stage-mcp.sh);
#        no secret is ever written — the token stays in ~/.config/splicedock/token.
"$RS" generate -g --targets claudecode --features rules
mcp_generate claudecode
"$RS" generate --targets codexcli --features rules -o "$HOME/.codex"
mcp_generate codexcli
# rulesync merges MCP servers and never removes one, so drop the pre-rename
# names (cellarette, cellarette-operator) once; a no-op when they are gone.
if command -v claude >/dev/null; then
  for s in cellarette cellarette-operator; do
    claude mcp remove -s user "$s" >/dev/null 2>&1 && echo "claude: removed legacy MCP server $s"
  done
fi
if command -v codex >/dev/null; then
  codex mcp remove cellarette >/dev/null 2>&1 && echo "codex: removed legacy MCP server cellarette"
fi
# Pi: rules only (rulesync's pi target has no MCP; Pi has no MCP client) plus our
# extensions. models.json/auth.json hold the LiteLLM key and stay host-local.
PI_DIR="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"
if command -v pi >/dev/null || [ -d "$PI_DIR" ]; then
  mkdir -p "$PI_DIR/extensions"
  "$RS" generate --targets pi --features rules -o "$PI_DIR"
  for f in pi/extensions/*.ts; do
    [ -f "$f" ] && cp -f "$f" "$PI_DIR/extensions/$(basename "$f")"
  done
  echo "pi: rules + $(ls pi/extensions/*.ts | wc -l) extension(s) synced to $PI_DIR"
fi

# Claude Code home: settings.json merge (plugins, env, hooks), hooks, RTK.md,
# rules/ tree. Additive; never touches permissions or secrets.
python3 scripts/claude-home.py sync

# Our hand-authored skills: copied byte-faithfully. rulesync's skill generator
# strips Claude-specific SKILL.md frontmatter (`args:`, folds `description`), so
# skills are versioned as plain files and cp'd, NOT routed through rulesync.
# Additive only — never touches the plugin-symlinked skills alongside them.
SKILLS_DST="$HOME/.claude/skills"
mkdir -p "$SKILLS_DST"
for d in skills/*/; do
  [ -d "$d" ] || continue
  dest="$SKILLS_DST/$(basename "$d")"
  rm -rf "$dest"          # replace, don't nest (cp into an existing dir creates dest/src)
  cp -a "${d%/}" "$dest"
  find "$dest" -name __pycache__ -type d -prune -exec rm -rf {} +
done
echo "skills: synced $(find skills -maxdepth 1 -mindepth 1 -type d | wc -l) to $SKILLS_DST"

# OpenCode agents (cross-review Reviewer B; gen-validate roles). One markdown file per
# agent, copied byte-faithfully. Additive: only same-named files are overwritten; the
# user's other agents and opencode.json are never touched.
OC_AGENT_DST="${OPENCODE_AGENT_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/opencode/agent}"
mkdir -p "$OC_AGENT_DST"
for f in opencode/agent/*.md; do
  [ -f "$f" ] || continue
  cp -f "$f" "$OC_AGENT_DST/$(basename "$f")"
done
echo "opencode agents: synced $(ls opencode/agent/*.md | wc -l) to $OC_AGENT_DST"

# optimAIzr (token-spend analysis, rule 60-optimaizr.md): pinned CLI in ~/.local (the npm
# global prefix /usr/local is root-owned) plus its Claude Code plugin (per-turn cost line,
# retry-loop guard). Idempotent. The statusline is NOT touched (ccstatusline stays).
OPTIMAIZR_VERSION="0.10.1"
if [ "$(optimaizr --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)" != "$OPTIMAIZR_VERSION" ]; then
  npm install -g --prefix "$HOME/.local" --no-fund --no-audit "optimaizr@$OPTIMAIZR_VERSION" >/dev/null
fi
echo "optimaizr: $(optimaizr --version 2>/dev/null | head -1)"
if command -v claude >/dev/null; then
  claude plugin marketplace list 2>/dev/null | grep -q optimaizr \
    || claude plugin marketplace add blendbunjaku/optimaizr >/dev/null
  claude plugin list 2>/dev/null | grep -q 'optimaizr@optimaizr' \
    || claude plugin install optimaizr@optimaizr >/dev/null
  echo "optimaizr: Claude Code plugin present"
fi

echo "agents synced."
