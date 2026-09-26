---
name: paperclip
description: >
  Work with the homelab's Paperclip agent company from Claude Code — the replacement for
  the retired Discord teammates. Hand a task to an agent (or to Hermes, the CEO, who
  delegates), ask an agent a question and wait for its answer, fetch a result, or get a
  status overview. Use when the user invokes /paperclip, or says "zleć / zapytaj / daj to
  agentowi / niech ops|medic|dev|hermes…", "co u agentów", "status Paperclipa".
---

# Paperclip from Claude Code

Paperclip (`https://paperclip.kamilandrzejrybacki.dpdns.org`, company prefix `HOM`) runs the
homelab's agents. You reach it through the MCP server **`paperclip`** (cellarette profile
`operator`): tools `paperclip__paperclip*` (board seat — you act as the operator) and
`n8n__cluster_snapshot` (deterministic health snapshot). If those tools are missing, tell
the user to restart Claude Code (MCP tools load at session start).

## Commands

Parse the user's words; Polish is fine. Default target agent is **hermes** (the CEO).

- `/paperclip task <text> [@agent]` — fire and forget.
  1. `paperclipListAgents` → resolve the agent name to its id (never guess ids).
  2. `paperclipCreateIssue` with `title` (≤80 chars, imperative), `description` (the full
     request + any context/links; say "read-only" when that is intended),
     `assigneeAgentId`, `status: "todo"` (todo wakes the agent).
  3. Reply with the identifier and link `…/HOM/issues/<IDENTIFIER>`. Done.
- `/paperclip ask <agent> <question>` — consult and WAIT for the answer.
  Create the issue as above, then poll `paperclipGetIssue` + `paperclipListComments`
  (order desc, limit 5) about every 60–90 s (use `sleep` in Bash between polls only if
  nothing else is useful). Stop when status is `done`/`cancelled`/`blocked` or after
  ~20 min; answer with the agent's final report (quote the key lines, keep its
  `OV:` line). On timeout, give the identifier and say it is still running.
- `/paperclip result HOM-N` — `paperclipGetIssue` + last comments; summarize the outcome.
- `/paperclip status` — `paperclipInboxLite` (what needs the operator),
  `paperclipListIssues` status `in_progress`/`blocked`, `paperclipListAgents` (any
  `error`/`paused`), and optionally `n8n__cluster_snapshot` for homelab health. One short
  table, problems first.

## Who does what

| Agent | For |
|---|---|
| hermes (CEO) | anything that needs splitting/delegation; strategy |
| ops | read-only diagnosis of the cluster/alerts |
| medic | fixes (approval-gated for risky actions) |
| dev, qa, security | code, CI failures, security review |
| research-lead (+ trends, market, competition, customer, viability) | research |
| scout, cataloger | feeds, SLM catalog |
| archivist | the canonical OpenViking doc |
| data, housekeeper, content-lead, writer | metrics/costs, disk, content |

## Rules

- **Your comments are board comments and WAKE the assignee.** Only comment to add real
  information or a follow-up request — never to acknowledge. Each wake costs tokens and,
  for Hermes and the terra agents, the ChatGPT subscription window.
- Do not close or re-assign agents' issues unless the user asks.
- Subscription agents (hermes, qa, security, research-lead on ChatGPT; medic, dev, writer
  on Claude) share limited 5-hour windows — prefer ops/data/research crew (DeepSeek) for
  bulk or repetitive asks.
- Never put secrets in an issue.
