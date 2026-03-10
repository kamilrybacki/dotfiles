#!/usr/bin/env bash

# i3lock-color with Everforest theme
# Uses the same wallpaper as the desktop

WALLPAPER="$HOME/.local/share/wallpapers/current.png"

/usr/local/bin/i3lock \
    --image="$WALLPAPER" \
    --fill \
    --clock \
    --indicator \
    --radius=120 \
    --ring-width=8 \
    --inside-color=2e383c00 \
    --ring-color=a7c080ff \
    --keyhl-color=83c092ff \
    --bshl-color=e67e80ff \
    --separator-color=37414500 \
    --insidever-color=2e383c00 \
    --ringver-color=83c092ff \
    --insidewrong-color=2e383c00 \
    --ringwrong-color=e67e80ff \
    --line-color=00000000 \
    --time-color=d3c6aaff \
    --date-color=d3c6aaff \
    --layout-color=d3c6aaff \
    --verif-color=83c092ff \
    --wrong-color=e67e80ff \
    --time-font="JetBrainsMono Nerd Font" \
    --date-font="JetBrainsMono Nerd Font" \
    --layout-font="JetBrainsMono Nerd Font" \
    --verif-font="JetBrainsMono Nerd Font" \
    --wrong-font="JetBrainsMono Nerd Font" \
    --time-size=48 \
    --date-size=14 \
    --noinput-text="" \
    --verif-text="..." \
    --wrong-text="✗" \
    --date-str="%A, %B %d"
