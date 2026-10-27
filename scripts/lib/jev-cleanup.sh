# Cleanup for hosts that ran the removed Jev decision layer. Sourced by
# scripts/bootstrap-agent-host.sh and scripts/agents-sync.sh. Idempotent:
# a host without Jev leftovers prints nothing destructive.
#
#   jev_cleanup <dotfiles-root>
#
# Strips jev-gate hook entries from ~/.claude/settings.json and
# ~/.codex/hooks.json, then removes the jev symlinks this repo used to create.
# It never deletes the API key; it only says it can be deleted.

jev_cleanup() {
  local root="$1" link target f
  python3 "$root/scripts/remove-jev-hooks.py" || return 1

  # Only symlinks whose target lives in a jev/ directory are ours.
  for link in "$HOME/.local/bin/jev-gate" "$HOME/.local/bin/jev-key-sync"; do
    if [ -L "$link" ]; then
      target="$(readlink "$link")"
      case "$target" in
        */jev/*) rm -f "$link"; echo "jev cleanup: removed symlink $link" ;;
      esac
    fi
  done

  local frag_dir="$HOME/.config/jev/fragments"
  if [ -d "$frag_dir" ]; then
    for f in "$frag_dir"/*; do
      [ -L "$f" ] || continue
      case "$(readlink "$f")" in
        */jev/*) rm -f "$f"; echo "jev cleanup: removed symlink $f" ;;
      esac
    done
    # Removes the directory only if it is now empty (local fragments stay).
    rmdir "$frag_dir" 2>/dev/null && echo "jev cleanup: removed empty $frag_dir" || true
  fi

  if [ -e "$HOME/.config/jev/api_key" ] || [ -e "$HOME/.config/jev/jev.env" ]; then
    echo "jev cleanup: NOTE ~/.config/jev/api_key and ~/.config/jev/jev.env are no longer used."
    echo "jev cleanup:       delete them when you are sure: rm ~/.config/jev/api_key ~/.config/jev/jev.env"
  fi
}
