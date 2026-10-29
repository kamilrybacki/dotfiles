#!/usr/bin/env bash
# Install jev-gate for the local harnesses (Claude Code, Codex CLI).
# Idempotent. Does NOT touch the API key - run ./jev-key-sync for that.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bin_dir="$HOME/.local/bin"
conf_dir="$HOME/.config/jev"

mkdir -p "$bin_dir" "$conf_dir/fragments"
ln -sfn "$here/bin/jev-gate" "$bin_dir/jev-gate"
ln -sfn "$here/jev-key-sync" "$bin_dir/jev-key-sync"
# Fragments are symlinked one by one so local-only fragments can live alongside.
for fragment in "$here"/fragments/*.md; do
  ln -sfn "$fragment" "$conf_dir/fragments/$(basename "$fragment")"
done

python3 "$here/register_hooks.py" "$@"
echo "jev-gate installed. Key: $( [[ -s $conf_dir/api_key || -n ${TYPESAFE_API_KEY:-} ]] && echo present || echo 'MISSING - run jev-key-sync')"
