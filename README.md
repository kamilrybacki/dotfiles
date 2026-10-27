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

## Agent setup — reproduce on any machine

The Claude Code + Codex setup (instructions, MCP servers, plugins, hooks,
settings, rules, graft) is rebuilt from this repo with one idempotent
command. Re-run it after every `git pull`.

```bash
git clone git@github.com:kamilrybacki/dotfiles.git ~/Code/dotfiles
cd ~/Code/dotfiles
npm run agents:bootstrap          # needs: claude, node/npm, python3, jq, git, curl
```

Homelab MCP tools work from anywhere: hosts other than lw-main talk to the
public cellarette edge (`https://cellarette-mcp.<domain>/mcp`, Bearer token);
lw-main uses its local `:8788` aggregator (`claude-home/hosts/lw-main.json`).
The token is never stored in this repo. Fetch it once per machine:

```bash
VAULT_ADDR=http://<vault>:8200 cellarette-token-sync   # on the LAN / WireGuard
cellarette-token-sync --stdin                          # anywhere else: paste it
```

The bootstrap prints whatever is left to do (token, PATH, Codex env var). Details: [`.rulesync/AGENTS-SYNC.md`](.rulesync/AGENTS-SYNC.md).

No SSH key on the machine? Clone over HTTPS instead
(`git clone https://github.com/kamilrybacki/dotfiles.git`, after `gh auth login`
and `gh auth setup-git`).

### Windows

Supported through WSL2 only; the bootstrap refuses Git Bash / MSYS. Everything
runs inside the distro and Claude Code is started from the WSL shell:

```bash
wsl --install -d Ubuntu                      # PowerShell, once; then open Ubuntu
sudo apt install -y git curl jq python3 unzip
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash   # then reopen the shell
nvm install --lts
curl -fsSL https://claude.ai/install.sh | bash   # Claude Code, Linux build
# gh: https://github.com/cli/cli/blob/trunk/docs/install_linux.md
```

Keep the clone in the Linux filesystem (`~/Code/dotfiles`, not `/mnt/c/...`).
WSL appends the Windows `PATH`; the bootstrap stops if `claude`, `node`, `npm`
or `python3` only resolve to a Windows binary under `/mnt/`. Logins (`claude`,
`gh`) are separate from the Windows ones and must be done inside WSL.

## Third-party agent harness on a laptop (agent-ds)

`scripts/setup-agent-ds.sh` creates an unprivileged WSL account `agent-ds` and
configures Claude Code there to use the homelab LiteLLM (DeepSeek-only key, capped)
and a read-only cellarette profile token (`deepseek-ro`), with `bypassPermissions`.

**Why a separate account:** the harness runs with permissions bypassed, so it must
never see your `~/.ssh`, `~/.kube`, or the full cellarette token. `agent-ds` has no
sudo, and the script sets your own home directory to `750` so `agent-ds` cannot read it. You keep sudo.

**Needs:** the WireGuard tunnel up, key-based `ssh` to lw-main (`kamil-rybacki@192.168.0.111`),
and LiteLLM reachable on the LAN. The script reads both secrets from Vault on lw-main;
it never prints them.

**Run** (as your normal user, not root; it calls `sudo` where needed):

```bash
bash scripts/setup-agent-ds.sh
```

It is idempotent. Re-run it after rotating a key. Start the harness with `sudo -iu agent-ds`, then `cd ~/work && claude`.

**Revoke:**

- LiteLLM: delete the virtual key with alias `laptop-agent-ds`.
- cellarette: revoke the `deepseek-ro` profile token (Vault `secret/homelab/cellarette/deepseek`).
- Local: `sudo deluser --remove-home agent-ds` removes the account and its files.

**Gotchas:**

- Claude Code assumes a 200k context window for models it does not know. The script sets
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW=100000` so auto-compaction fires before DeepSeek's real limit.
- DeepSeek self-identifies as Claude. Do not use the model's answer about its own identity as evidence of which backend served the request.
- Claude Code rewrites `~/.claude/settings.json` on first start. The script merges only
  `permissions.defaultMode` with `jq` after that, so re-running it restores the bypass mode without touching the rest.
- The first start asks once to confirm bypass-permissions mode.

## Cross-model review and data validation

Two skills, both shipped by `agents:sync` to Claude Code on every host.

| Role | Model | Tool | When |
|---|---|---|---|
| Implementer | Claude | Claude Code / T3 Code | always |
| Reviewer A | Codex: `gpt-6-luna` (rank 1-2), `gpt-6.1-sol` (rank 3) | `codex exec`, read-only sandbox | always |
| Reviewer B | Kimi K3 (OpenCode Go, agent `reviewer`) | `opencode run --agent reviewer` | rank >= 2 and data not restricted |
| Generator / judges (bulk data) | `deepseek/deepseek-chat`, `groq/gpt-oss-120b` | LiteLLM (`gen-validate`) | data labelling only, never OpenCode Go |

**Rank rules** (`skills/cross-review/rank.sh`, deterministic; the skill may raise, never lower):

- rank 1: docs or tests only, <= 150 changed lines. Codex luna low. Reviewer B skipped.
- rank 2: normal feature or bugfix. Codex luna medium + Reviewer B.
- rank 3: security/auth/crypto, infra/CI/helm/ansible/argocd/terraform, secrets, DB
  migrations, public API/contracts, dependency or lockfiles, or > 400 changed lines.
  Codex sol medium + Reviewer B.

**Sensitivity gate.** Tier = max(deterministic rules, jev), from `skills/cross-review/sensitivity.py`.
Deterministic restricted hits always win: infra paths (helm, charts, ansible, argocd,
terraform, k8s, `.github/workflows`, Dockerfile, compose), secrets paths (`.env`, `*secret*`,
`*credential*`, keys, vault, sops), network paths (wireguard, caddy, cloudflared, iptables,
ufw, `/etc`), and content with private keys, tokens, or 192.168.x / 10.x addresses.
jev "restricted" also wins. jev "uncertain" or unavailable with clear rules gives
`standard` (cross-review may use Reviewer B). `restricted` means no OpenCode Go reviewer
and no open or Chinese model. Codex is first-party and still runs. For gen-validate,
jev uncertain needs an operator-confirmed `--data-class open`. Restricted data is refused even with the flag.

**Go vs LiteLLM.** The OpenCode Go subscription is for interactive coding only. Bulk
generation and judging go through the homelab LiteLLM API (`gen-validate` refuses
OpenCode Go endpoints). `opencode/agent/` ships only `reviewer`.

**Use it from T3 Code.**

- Claude thread: finish the change, commit, then run `/cross-review [base-ref]` in the
  same thread. Claude consolidates and fixes. Max 3 rounds.
- OpenCode thread: `@reviewer` reviews the current diff read-only. Its answer ends in a
  `VERDICT:` line. It does not edit or run commands.
- Data labelling: run `/gen-validate` in a Claude thread. It is not an OpenCode agent.

**Install** (on each host, lw-main and the WSL laptop):

```bash
git pull && npm run agents:sync
```

The sync copies `skills/cross-review` and `skills/gen-validate` into `~/.claude/skills/`
and `opencode/agent/*.md` into `~/.config/opencode/agent/`. It never deletes files.
Restart OpenCode after syncing.

**Needs:** `codex` (Codex CLI), `opencode` 1.19+ (for Reviewer B), `jev-gate`,
`python3`. Vault access on lw-main for the LiteLLM key, or `LITELLM_GEN_KEY`.
