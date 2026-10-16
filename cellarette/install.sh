#!/usr/bin/env bash
# Link the cellarette helpers into ~/.local/bin. Idempotent. Run by
# `npm run agents:sync`; does NOT fetch the token (run cellarette-token-sync).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bin_dir="$HOME/.local/bin"
mkdir -p "$bin_dir"
ln -sfn "$here/cellarette-headers" "$bin_dir/cellarette-headers"
ln -sfn "$here/cellarette-token-sync" "$bin_dir/cellarette-token-sync"
