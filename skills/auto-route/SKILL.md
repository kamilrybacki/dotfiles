---
name: auto-route
description: >
  Auto mode for T3 Code (like Nexos.ai "auto"): from this point in the session, every task the
  user gives is classified by Jev with two questions — the role (design → Claude, implement →
  DeepSeek via opencode, review → GPT via codex, mechanical → free Pi) and the criticality of
  the feature (→ effort low/medium/high/max) — and delegated with `delegate_task` to the matching
  provider, model and effort. Implementation always gets an adversarial GPT review except at low
  effort. Use when the user invokes /auto-route, or says "auto mode", "routuj zadania",
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

   It prints `{role, effort, sensitivity, target, fallback, review, reasons, probabilities}`.
   `route.py` is a thin wrapper over `jev-gate model-route`, the same code the hooks use.
   Role `answer` means: reply directly, no target.

   **In T3 top-level threads the hooks already did this step:** the prompt arrives with an
   `Auto-route` context block that holds the route, so use it and skip the call. A
   `delegate_task` to a model outside that route's target, fallback or reviewer is denied
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

Role → family (question 1). Criticality → effort (question 2):
trivial → low, limited → medium, material → high, critical → max.

| effort | design (Claude) | implement (opencode DeepSeek) | review / adversarial (codex GPT) |
|---|---|---|---|
| low | Haiku 5.5 · medium | deepseek-v4.1-flash · low (no review) | gpt-6-luna · medium |
| medium | Sonnet 5.5 · medium | deepseek-v4.1-flash · high | gpt-6.1-terra · medium |
| high | Sonnet 5.5 · high | deepseek-v4.1-flash · high | gpt-6.1-sol · high |
| max | Opus 5.5 · high | deepseek-v4.1-flash · high | gpt-6.1-sol · high |

The implement reviewer is the GPT model in the same row. Mechanical → Pi `default` (free),
fallback Haiku. Capacity fallbacks: design ↔ GPT of the same row, review ↔ Claude of the same
row, implement → Claude of the same row.

**Astra, Fable and the top efforts (`xhigh`, `max`) are never routed.** Any delegation to them (delegate_task or the Agent tool) asks the operator to confirm, even with "bez routingu" or routing off. The "max" route level therefore uses effort `high`.

**Restricted** sensitivity (no opencode, Pi, Haiku or Luna; low is raised to medium):

| effort | design | implement → reviewer | review | mechanical |
|---|---|---|---|---|
| low / medium | Sonnet · medium | gpt-6.1-terra · medium → Sonnet · medium (none at low) | terra · medium | terra · medium |
| high | Sonnet · high | gpt-6.1-sol · high → Sonnet · high | sol · high | sol · high |
| max | Opus · high | gpt-6.1-sol · high → Opus · high | sol · high | sol · high |

Decision rule (in `route.py`):
- Role = the most likely option. P(other) ≥ 0.5 or no answer → design (you decide).
  Mechanical needs P ≥ 0.7, otherwise implement.
- Effort = the lowest criticality level whose cumulative probability (ignoring `other`) reaches
  0.7. `max` also needs P(critical) ≥ 0.5, otherwise high. P(other) ≥ 0.5 or no answer → medium.
- Sensitivity from `jev-gate route`; unreachable or unsure → restricted.

## Runtime rules

- **Capacity failure** (quota, rate limit, provider down) → same task to `fallback`. Not a sign
  of difficulty; it does not count as an escalation.
- **Missing access/credentials/requirements** → resolve the blocker or ask; a bigger model
  cannot fix missing access.
- **Failed checks or unsupported conclusions** → one correction round with the concrete
  evidence, only if the feedback names a concrete fix.
- **Repeated substantive failure** → escalate to the next effort row of the same role (no need
  to rerun `route.py`) with a compact handoff: findings, attempted fixes, failing checks. At
  most two escalations; after `max`, implementation moves to Claude of the max row. Then report
  the unresolved issue.
- **Weak presentation only** → ask for the missing evidence/format; do not escalate.
- **Follow-ups** to the same objective stay on the successful target. Reclassify (with
  `--history`) when scope, sensitivity or failure evidence changes.

## Hard rules

- **Sensitivity.** `restricted` work (secrets, `.env`, infra config, network topology) never
  goes to `pi`, `opencode`, Haiku or Luna — not as target, fallback, reviewer or escalation.
  If the user overrides to such a model for restricted work, refuse that part and say why.
- **User override wins** otherwise ("zrób to Codexem", "użyj Opusa", "bez delegowania") for
  that task; auto mode continues with the next one.
- Never put secrets into the fields passed to `route.py`; they are sent to Jev.
- Thresholds are starting values, not calibration. When a route turns out wrong, tell the user
  which threshold or criterion misfired so it can be tuned in `route.py`.
