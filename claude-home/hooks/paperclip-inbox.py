"""SessionStart hook: Paperclip items waiting for the operator -> additionalContext."""
import json
import os
import re
import sys
import urllib.request

URL = "https://cellarette-mcp.kamilandrzejrybacki.dpdns.org/mcp"


def call(auth, status):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "paperclip__paperclipListIssues", "arguments": {"status": status}}}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": auth, "content-type": "application/json", "accept": "application/json, text/event-stream",
        "user-agent": "claude-code-paperclip-hook/1.0"})
    text = urllib.request.urlopen(req, timeout=6).read().decode()
    m = re.search(r"data: (.*)", text)
    payload = json.loads(m.group(1) if m else text)
    inner = json.loads(payload["result"]["content"][0]["text"])
    return inner if isinstance(inner, list) else inner.get("issues", [])


def main():
    # Token of the cellarette `operator` profile. Kept outside ~/.claude.json: a running
    # Claude Code session rewrites that file from memory and drops hand-added entries.
    token = open(os.path.expanduser("~/.config/paperclip/operator-token")).read().strip()
    auth = f"Bearer {token}"
    rows = []
    for status in ("in_review", "blocked", "todo"):
        rows += call(auth, status)
    items, seen = [], set()
    for i in rows:
        waiting = i.get("status") in ("in_review", "blocked") or (i.get("status") == "todo" and not i.get("assigneeAgentId"))
        if not waiting or i["identifier"] in seen:
            continue
        seen.add(i["identifier"])
        items.append(f"- {i['identifier']} [{i['status']}] {i.get('title', '')[:70]}")
    if not items:
        return
    ctx = (f"Paperclip (agent company) items waiting for the operator: {len(items)}. "
           "Mention this briefly at the start of the session; /paperclip acts on them.\n" + "\n".join(items[:12]))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # never break session start
        if os.environ.get("PAPERCLIP_HOOK_DEBUG"):
            print(f"paperclip-inbox: {exc}", file=sys.stderr)
