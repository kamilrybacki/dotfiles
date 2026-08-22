# Claude Code plugin manifest

Declarative list of the plugin marketplaces + plugins this setup uses, so a fresh
machine restores the exact same set. Third-party plugins are **not vendored** —
they stay upstream and update normally; this manifest just re-adds and re-installs
them.

- `marketplaces.txt` — `name<TAB>github-repo`, one per line.
- `plugins.txt` — `plugin@marketplace`, one per line.
- `restore.sh` — re-adds every marketplace and installs every plugin via the `claude` CLI.

## Restore on a new machine

```bash
./restore.sh          # claude plugin marketplace add … && claude plugin install …
claude plugin list    # verify
```

## Update the manifest after installing/removing plugins

Regenerate from the live state:

```bash
python3 - <<'PY'
import json
mk=json.load(open(f"{__import__('os').path.expanduser('~')}/.claude/plugins/known_marketplaces.json"))
pl=json.load(open(f"{__import__('os').path.expanduser('~')}/.claude/plugins/installed_plugins.json"))
open('marketplaces.txt','w').write(''.join(f"{n}\t{v['source'].get('repo','')}\n" for n,v in sorted(mk.items())))
open('plugins.txt','w').write(''.join(k+"\n" for k in sorted(pl['plugins'])))
PY
```

Bulk of the reusable skills (design set, tdd, review, deep-research, grill-me, …)
come from these plugins — that is why `~/.claude/skills/` is mostly symlinks into
plugin caches. Our own hand-authored skills live in `.rulesync/skills/` and ship
via `npm run agents:sync`.
