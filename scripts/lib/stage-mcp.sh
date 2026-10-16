# Sourced by agents-sync.sh / agents-check.sh (cwd = dotfiles root, $RS set).
# mcp_generate <claudecode|codexcli> [rulesync flags...]
#   Copies the rulesync sources to a temp dir, pins the cellarette server to this
#   host (claude-home.py render-mcp) and runs `rulesync generate -g` for the MCP
#   feature from there, so the committed .rulesync/mcp.jsonc stays host-neutral.
mcp_generate() {
  local target="$1"; shift
  local rs stage rc=0
  rs="$(cd "$(dirname "$RS")" && pwd)/$(basename "$RS")"
  stage="$(mktemp -d)"
  cp -a .rulesync rulesync.jsonc "$stage/"
  python3 scripts/claude-home.py render-mcp "$stage/.rulesync/mcp.jsonc" "$target" >/dev/null
  (cd "$stage" && "$rs" generate -g --targets "$target" --features mcp "$@") || rc=$?
  rm -rf "$stage"
  return "$rc"
}
