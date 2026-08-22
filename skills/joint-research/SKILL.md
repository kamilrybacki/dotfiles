---
name: joint-research
description: >
  Two-agent joint research: Claude Code AND the Hermes homelab agent research the same
  topic in parallel from complementary angles, then Claude merges both into a single
  report. Use when the user invokes /joint-research or asks for research "with Hermes",
  "joint research", or "both of you look into". Requires cellarette discord__* +
  exa__* tools and a live Hermes gateway.
metadata:
  version: "1.0.0"
  last_updated: "2026-07-14"
  status: active
  requires: "cellarette MCP (discord__*, exa__*), Hermes agent live in ns hermes"
  related_skills:
    - deep-research
---

# Joint Research — Claude × Hermes

Parallel two-agent research with a merged report. You (Claude) are the **orchestrator
and synthesizer**; Hermes is a **peer researcher** with different strengths — use them.

**Division of strengths** (default; adapt to topic):
- **Claude**: broad + fresh web sweep (exa search/fetch), codebase/repo inspection (gh),
  structured synthesis, adversarial source-checking.
- **Hermes**: its Obsidian research vault (`/opt/knowledge-vault/content/research/` —
  prior notes on adjacent topics), its holographic memory of the homelab, its own
  exa/lightpanda/context7 tools, and homelab-context judgment (what actually fits
  this infrastructure).

## Protocol (6 phases)

### 1. Scope (with user, ~1 exchange max)
Restate the topic as 1-3 research questions. If the request is unambiguous, don't
interrogate — state the questions and proceed. Generate a short run id:
`jr-<slug>-<ddhhmm>` (no Date.now in scripts — read the clock via `date`).

### 2. Decompose + dispatch to Hermes
Split the questions into two **complementary** briefs (not copies):
- Claude brief: breadth, freshness, external sources, quantitative claims.
- Hermes brief: depth on the homelab/agent-relevant angle, its vault + memory recall,
  its independent web pass on the subquestions Claude is NOT covering.

Send Hermes its brief via `discord__discord_send` to #hermes
(channelId `1525886749627125821`), starting with the mention
`<@1525870647501262949>`. The message MUST include:
- the run id and topic;
- its subquestions (bulleted, concrete);
- deliverable format: markdown with `## Findings`, `## Sources` (URLs), `## Confidence
  & gaps`;
- the completion marker: *"End your final message with `JOINT-RESEARCH <run-id>
  COMPLETE`"*;
- a soft deadline ("aim for ~15 minutes; partial findings beat silence");
- "reflection/research only — no infra actions".

### 3. Research your half (in parallel, immediately)
Do NOT wait for Hermes before starting. Work your brief:
- 3-6 `exa__web_search_exa` queries phrased as ideal-page descriptions; follow up with
  `web_fetch_exa` on the best hits.
- For repo/code topics: `gh__run` reads (issue/pr/search; `repo view` and `api` are
  denied — use search).
- Track every claim → source URL. Note confidence per finding. Prefer primary sources;
  flag anything single-sourced.

### 4. Collect Hermes' findings
Poll `discord__discord_read_messages` on #hermes (limit 10-20) every ~2-3 minutes
(use waiting patterns available in your environment; do not busy-loop). Look for the
completion marker or a substantive reply mentioning the run id. Hermes may split long
answers across messages and may reply inside an auto-thread — if the channel shows a
thread stub, read the thread channelId too.
- **Timeout**: after ~25 minutes without the marker, send ONE nudge mention. After
  ~10 more minutes, proceed solo and mark the report "Hermes: no response —
  single-agent findings only".
- If Hermes replies it lacks a tool/capability, note it, fold its partial answer in.

### 5. Cross-examine + synthesize
This is the value of two agents — do not just concatenate:
- Diff the two result sets: agreements (high confidence), conflicts (investigate —
  quick targeted search to adjudicate, cite the winner), unique finds per agent.
- Attribute: mark findings `[C]` (Claude), `[H]` (Hermes), `[C+H]` (independently
  corroborated — strongest tier).
- Kill weak claims: anything single-sourced AND unverifiable gets moved to an
  "Unverified leads" section, not silently dropped.

### 6. Report + deliver
Write `joint-research-<run-id>.md` in the cwd (or user-specified path):

```markdown
# <Topic> — Joint Research Report
run: <run-id> · date · agents: Claude Code + Hermes
## Executive summary        (≤10 lines, corroboration-tier first)
## Key findings             (each: claim, [C]/[H]/[C+H], sources)
## Conflicts & adjudication (what disagreed, how resolved)
## Unverified leads
## Hermes' perspective      (its homelab-context judgment, quoted/summarized)
## Sources                  (deduped, both agents)
## Method note              (briefs given, timing, any timeout/partial)
```

Then:
- send the file to the user (SendUserFile if available);
- post a ≤8-line summary to #hermes crediting both agents, ending with
  `JOINT-RESEARCH <run-id> PUBLISHED`;
- if the user wants it in the knowledge vault, use `obsidian__obsidian_append_content`
  to add it under `research/` (Quartz publishes that folder).

## Rules
- Never block on Hermes to start your own research — parallel or it's pointless.
- Never dispatch infra-touching instructions to Hermes inside a research brief.
- Hermes' findings are evidence, not gospel — verify anything surprising before it
  enters "Key findings" above the unverified tier.
- One nudge max; a hung Hermes must not hang the skill.
- Keep the Discord brief self-contained — Hermes has no access to this conversation.
