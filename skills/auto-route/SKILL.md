---
name: auto-route
description: >
  Auto mode for T3 Code (like Nexos.ai "auto"): from this point in the session, every task the
  user gives is classified by Jev with two questions — the role (design → Claude, implement →
  DeepSeek via opencode, review → GPT via codex, mechanical → free Pi) and the criticality of
  the feature (→ model tier T1–T3, lowered under subscription budget pressure) — and delegated with `delegate_task` to the matching
  provider, model and effort. Implementation gets a cross-vendor review except for trivial
  work. Use when the user invokes /auto-route, or says "auto mode", "routuj zadania",
  "rozdzielaj zadania automatycznie".
---

# Auto-route

Once invoked, this stays on for the rest of the thread until the user says "auto-route off"
(or "wyłącz auto mode"). Acknowledge activation in one line and wait for the first task.

The division of labour: **Claude orchestrates and designs, DeepSeek implements, GPT reviews
adversarially.** You (the orchestrator) are the Claude side; you plan, brief, integrate and
fix small findings.

## For every user task

1. **Answer inline instead** when the task is a short question you can answer from the current
   context, with nothing to edit or investigate. Delegating that costs more than it saves.

2. **Classify.** Fill sanitized fields (no secrets, tokens or file contents; write `unknown`
   rather than guessing) and run:

   ```bash
   python3 -I ~/.claude/skills/auto-route/route.py "<1-3 sentence task summary>" \
     --deliverable "<patch | plan | review | answer | runbook…>" \
     --scope "<e.g. 1 file in api/, 3 services, unknown>" \
     --history "<none | follow-up of implement/high task | failed: <one line>>" \
     --file <path the task touches> [--file …]
   ```

   Pass `--file` for the paths you know: without them the sensitivity check is often unsure and
   then falls back to `restricted`. (Paths only, never contents.)

   It prints `{role, effort, tier, sensitivity, target, fallback, review, escalate, budget, reasons, probabilities}`.
   `route.py` is a thin wrapper over `jev-gate model-route`, the same code the hooks use.
   Role `answer` means: reply directly, no target.

   **In T3 top-level threads the hooks already did this step:** the prompt arrives with an
   `Auto-route` context block that holds the route, so use it and skip the call. A
   `delegate_task` to a model outside that route's target, fallback, reviewer or escalation is denied
   by a PreToolUse hook. If you edit files for an implement/review/mechanical prompt without
   any `delegate_task`, a Stop hook stops you once: delegate, or tell the user why inline was
   right. The user overrides all of this for one prompt with "bez routingu".

3. **Announce the route** in one line, e.g.
   `→ implement · material/high (standard) → opencode · deepseek-v4.1-flash · high; review → codex · gpt-6.1-sol · high`,
   plus `reasons` if any.

4. **Act by role.** Call `orchestrator_capabilities` once per thread before the first
   delegation. Every `delegate_task` gets `target` = the JSON target verbatim and a
   self-contained brief (goal, relevant paths, constraints, what is ruled out, acceptance
   checks; the child sees none of this thread). `isolation: "worktree"` for changes that touch
   many files or might conflict with the user's work in progress, otherwise `shared`;
   `mode: "wait"` for short tasks, `async` for long ones (follow the returned `next`, never poll).
   - **design**: if the target is the model you are running on, or weaker, do it inline;
     otherwise delegate. When the plan leads to code, route each implementation step separately.
   - **implement**: delegate to the target with the plan as the brief. Then, when `review` is
     not null, start a **separate** `delegate_task` to the `review` target: only the diff, the
     goal and the acceptance checks, asking it to break the change (correctness, security,
     edge cases, missing tests). Fix small findings yourself; send larger ones back to the
     implementer with the evidence.
   - **review**: delegate to the target with the artifact and what it must hold; report the
     findings, do not fix unasked.
   - **mechanical**: delegate to the target (Pi); check the result yourself.

5. **Report**: what was done, by which model, review findings.

## Routing tables

Every route is a **tier**, not a fixed model. Criticality → tier per role:

| tier | Claude ladder | GPT ladder | DeepSeek ladder (implement) |
|---|---|---|---|
| T1 cheap | Haiku 5.5 · medium | gpt-6-luna · medium | deepseek-v4.1-flash · low |
| T2 default | Sonnet 5.5 · medium | gpt-6.1-terra · medium | deepseek-v4.1-flash · high |
| T3 strong | Opus 5.5 · high | gpt-6.1-sol · high | gpt-6.1-sol · high |
| T4 top | Astra, Fable, any `xhigh`/`max` | — | — |

| criticality | design (Claude) | implement (DeepSeek) | review (GPT) | implement reviewer |
|---|---|---|---|---|
| trivial | T2 | T1 | T1 | none |
| limited | T2 | T1 | T1 | T1 |
| material | T3 | T2 | T2 | T2 |
| critical | T3 | T2 | T3 | T3 |

The implement reviewer is from another vendor than the implementer (DeepSeek → GPT, Codex →
Claude). Mechanical → Pi `default` (free), fallback Haiku. Capacity fallback = the other
vendor's ladder at the same tier. **Escalate** = the same ladder one tier up (in the route).

**T4 is never routed.** Any delegation to Astra, Fable or the top efforts (`xhigh`, `max`),
via delegate_task or the Agent tool, asks the operator to confirm, even with "bez routingu" or
routing off.

**The thread itself:** most prompts are design. Run the T3 Code thread on Sonnet by default; Opus
only when the route says T3. At T1/T2 an Opus thread should delegate instead of working inline.

**Budget pressure** (`jev_gate/budget.py`) reads the quota-axi cache
(`~/.cache/quota-axi/quotas.json`). Per provider it projects the worst window's usage at reset
(used / elapsed fraction): < 80 % → 0, < 100 % → 1, < 130 % → 2, else (or used ≥ 90 %) → 3.
Non-critical work drops one tier per level (at most two; design never below T2). Critical
work is never lowered. Level 3 swaps to the other vendor's ladder when that one is not burning.
No or stale cache → no pressure. Snapshots go to `~/.local/state/jev/usage.jsonl` (every
10 min) for trends.

**Restricted** sensitivity: first-party only, no opencode, Pi or Luna. Haiku is allowed.
Implement ladder: T1 Haiku, T2 Terra, T3 Sol (reviewer Claude); GPT ladder T1 is Terra;
mechanical → Haiku (fallback Terra).

Decision rule (in `route.py`):
- Role = the most likely option. P(other) ≥ 0.5 or no answer → design (you decide).
  Mechanical needs P ≥ 0.7, otherwise implement.
- Criticality = the lowest level whose cumulative probability (ignoring `other`) reaches
  0.5 (the median). `critical` also needs P(critical) ≥ 0.5, otherwise material. P(other) ≥ 0.5 or no answer → limited.
- Sensitivity from `jev-gate route`; unreachable or unsure → restricted.

## Runtime rules

- **Capacity failure** (quota, rate limit, provider down) → same task to `fallback`. Not a sign
  of difficulty; it does not count as an escalation.
- **Missing access/credentials/requirements** → resolve the blocker or ask; a bigger model
  cannot fix missing access.
- **Failed checks or unsupported conclusions** → one correction round with the concrete
  evidence, only if the feedback names a concrete fix.
- **Failing tests or a rejecting review after the correction round** → escalate automatically,
  **once**, to the route's `escalate` target (one tier up, the hook allows it) with a compact
  handoff: findings, attempted fixes, failing checks. No further escalation without the user;
  report the unresolved issue.
- **Weak presentation only** → ask for the missing evidence/format; do not escalate.
- **Follow-ups** to the same objective stay on the successful target. Reclassify (with
  `--history`) when scope, sensitivity or failure evidence changes.

## Hard rules

- **Sensitivity.** `restricted` work (secrets, `.env`, infra config, network topology) never
  goes to `pi`, `opencode` or Luna — not as target, fallback, reviewer or escalation.
  If the user overrides to such a model for restricted work, refuse that part and say why.
- **User override wins** otherwise ("zrób to Codexem", "użyj Opusa", "bez delegowania") for
  that task; auto mode continues with the next one.
- Never put secrets into the fields passed to `route.py`; they are sent to Jev.
- Thresholds are starting values, not calibration. When a route turns out wrong, tell the user
  which threshold or criterion misfired so it can be tuned in `route.py`.
