#!/usr/bin/env bash
# Link the splicedock helpers into ~/.local/bin. Idempotent. Run by
# `npm run agents:sync`; does NOT fetch the token (run splicedock-token-sync).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bin_dir="$HOME/.local/bin"
mkdir -p "$bin_dir"
ln -sfn "$here/splicedock-headers" "$bin_dir/splicedock-headers"
ln -sfn "$here/splicedock-token-sync" "$bin_dir/splicedock-token-sync"
ln -sfn "$here/codex-splicedock" "$bin_dir/codex-splicedock"

# Pre-rename leftovers (the gateway was called cellarette until 2026-11):
# drop the old helper links and move the token dir, leaving a compat symlink.
for old in cellarette-headers cellarette-token-sync codex-cellarette; do
  [ -L "$bin_dir/$old" ] && rm -f "$bin_dir/$old"
done
cfg="${XDG_CONFIG_HOME:-$HOME/.config}"
if [ -d "$cfg/cellarette" ] && [ ! -L "$cfg/cellarette" ] && [ ! -e "$cfg/splicedock" ]; then
  mv "$cfg/cellarette" "$cfg/splicedock"
  ln -s splicedock "$cfg/cellarette"
  echo "splicedock: moved $cfg/cellarette -> $cfg/splicedock"
fi
