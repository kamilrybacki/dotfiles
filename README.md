# dotfiles — Everforest Dark i3

> Cozy tiling WM setup themed around [Everforest Dark](https://github.com/sainnhe/everforest) with a ditherpunk/D&D aesthetic.

![Everforest Dark](https://img.shields.io/badge/theme-Everforest%20Dark-a7c080?style=flat-square&labelColor=2e383c)
![i3wm](https://img.shields.io/badge/WM-i3wm-7fbbb3?style=flat-square&labelColor=2e383c)
![Polybar](https://img.shields.io/badge/bar-Polybar-d699b6?style=flat-square&labelColor=2e383c)

## Components

| Role | Tool |
|------|------|
| Window manager | [i3wm](https://i3wm.org/) |
| Status bar | [Polybar](https://github.com/polybar/polybar) |
| Launcher | [Rofi](https://github.com/davatorium/rofi) |
| Notifications | [Dunst](https://dunst-project.org/) |
| Terminal | [Kitty](https://sw.kovidgoyal.net/kitty/) |
| System info | [Fastfetch](https://github.com/fastfetch-cli/fastfetch) |
| Shell | Zsh + Oh My Zsh + Powerlevel10k |
| Colors | Xresources (Everforest Dark palette) |
| Lockscreen | [i3lock-color](https://github.com/Raymo111/i3lock-color) |

## Color Palette

All colors come from a single source of truth: `.Xresources`.
Both i3 and Polybar read colors via `xrdb` at startup.

| Name | Hex | Use |
|------|-----|-----|
| `bg_dim` | `#272e33` | Polybar background |
| `bg0` | `#2e383c` | Window background |
| `bg1` | `#374145` | Inactive borders |
| `fg` | `#d3c6aa` | Text |
| `green` | `#a7c080` | Focused border, accents |
| `aqua` | `#83c092` | Secondary accent |
| `blue` | `#7fbbb3` | Tertiary accent |
| `red` | `#e67e80` | Urgent / errors |

## Layout

```
~/ (home directory)
├── .Xresources              ← color palette (source of truth)
├── .zshrc                   ← shell config
├── .config/
│   ├── i3/config            ← i3wm config
│   ├── polybar/
│   │   ├── config.ini       ← bar layout & modules
│   │   └── launch.sh        ← multi-monitor launcher
│   ├── rofi/
│   │   ├── config.rasi      ← rofi settings
│   │   └── everforest.rasi  ← rofi theme
│   ├── dunst/dunstrc        ← notification style
│   ├── kitty/
│   │   ├── kitty.conf       ← terminal config
│   │   └── everforest.conf  ← terminal colors
│   └── fastfetch/config.jsonc
└── .local/bin/
    └── lock.sh              ← i3lock-color with Everforest theme
```

## Install

```bash
git clone https://github.com/kamilrybacki/dotfiles ~/dotfiles
cd ~/dotfiles
bash install.sh
```

The install script symlinks each file to its correct location.
Existing files are backed up with a `.bak` suffix.

## Dependencies

```
i3 i3lock-color polybar rofi dunst kitty fastfetch
zsh oh-my-zsh nitrogen xss-lock feh pactl
JetBrainsMono Nerd Font  Papirus icon theme
```

On Debian/Ubuntu-based systems:
```bash
sudo apt install i3 polybar rofi dunst kitty zsh nitrogen xss-lock pulseaudio-utils
# i3lock-color must be built from source: https://github.com/Raymo111/i3lock-color
# fastfetch: https://github.com/fastfetch-cli/fastfetch/releases
```

## Secrets

Tokens and API keys are **never** stored here.
Put them in `~/.zshrc.secrets` (untracked):

```bash
# ~/.zshrc.secrets
export GITHUB_PAT=your_token_here
```

Your `.zshrc` will source that file automatically if it exists.
