---
name: route
description: Advise which agent should do a task (claude, codex, opencode_kimi, pi_free, or other). Asks Jev one typed choice question, prints the probabilities, applies hard overrides for infra, secrets and customer data, and recommends. Advisory only: it never starts anything. Use on /route <task description>, or when asked which agent should take a task.
user-invocable: true
---

# route

Advisory only. Print the recommendation and stop. Never start, delegate or run a task
from this skill.

Options:

| Key | Use for |
|---|---|
| `claude` | first-party Claude. Infra, secrets and customer data allowed |
| `codex` | first-party Codex. Code and review. Infra and secrets allowed |
| `opencode_kimi` | open model (Kimi K3, OpenCode Go). Code only, no infra or secrets |
| `pi_free` | Pi on free or cheap LiteLLM models. Bulk, trivial and data tasks |
| `other` | none of these |

## Steps

1. **Summary.** Write at most 3 plain sentences describing the task. No code, no paths,
   no credentials, no hostnames, no IPs, no customer data. Do not paste the raw task if it
   contains any of those. Summarize it in general terms.

2. **Question.** Run
   `python3 "$SKILL/route.py" question --summary "<summary>"`.
   It prints a JSON request with one `owner` choice question. Use exactly that JSON.

3. **Ask Jev.** Call `mcp__cellarette__jev__ask` with its `state` and `questions`.
   Save the whole response to `answer.json`. If the call fails, print "Jev unavailable"
   and give your own recommendation with reasons. Stop there.

4. **Format.** Save the raw task text to `task.txt` in a scratch dir (it stays local and is
   never sent). Run
   `python3 "$SKILL/route.py" format --task-file task.txt --answer answer.json`.
   It prints the sorted probabilities, the confidence, and a recommendation. Hard overrides
   run first: if the task mentions infra, secrets, Vault, helm, ansible, network, customer
   data and similar terms, `opencode_kimi` and `pi_free` are excluded, and the output says why.

5. **Report.** Print the script output as is. If it says "Jev is unsure", add your own
   recommendation, with reasons. Do not start the chosen agent. Say that the user decides.

Jev is a third-party service. Advisory only: never a gate, and not used for gen-validate labels.
