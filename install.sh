#!/usr/bin/env bash
# install.sh — symlink dotfiles into $HOME

set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

link() {
    local src="$DOTFILES/$1"
    local dst="$HOME/$1"
    local dir
    dir=$(dirname "$dst")

    mkdir -p "$dir"

    if [[ -e "$dst" && ! -L "$dst" ]]; then
        echo "  backup  $dst -> ${dst}.bak"
        mv "$dst" "${dst}.bak"
    fi

    ln -sfn "$src" "$dst"
    echo "  linked  $dst"
}

echo "Installing dotfiles from $DOTFILES ..."
echo

link ".Xresources"
link ".zshrc"
link ".config/i3/config"
link ".config/picom/picom.conf"
link ".config/polybar/config.ini"
link ".config/polybar/launch.sh"
link ".config/rofi/config.rasi"
link ".config/rofi/everforest.rasi"
link ".config/dunst/dunstrc"
link ".config/kitty/kitty.conf"
link ".config/kitty/everforest.conf"
link ".config/fastfetch/config.jsonc"
link ".local/bin/lock.sh"

chmod +x "$HOME/.local/bin/lock.sh"
chmod +x "$HOME/.config/polybar/launch.sh"

echo
echo "Done! Reload i3 with: i3-msg reload"
