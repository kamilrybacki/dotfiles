---
name: gen-validate
description: Bulk labelled-data generation with independent-judge validation. A cheap generator labels each item, two judges from different vendors check every label, only items both accept are kept, and Claude spot-checks a random sample. Reports agreement rate and cost. Runs ONLY through the homelab LiteLLM API, never OpenCode Go. Use for generating or validating training/eval labels in bulk.
user-invocable: true
---

# gen-validate

Bulk traffic goes through the homelab LiteLLM OpenAI-compatible API
(`http://192.168.0.60:30400/v1`). The OpenCode Go subscription is for interactive
coding only and is refused here by the script.

Pipeline: generator labels each item -> judge A and judge B each check it -> keep
items both accept -> sample kept items for Claude spot-check -> report.

Defaults: generator `deepseek/deepseek-chat`; judges `deepseek/deepseek-chat` and
`groq/gpt-oss-120b` (different vendors). Override with `--generator`, `--judge-a`, `--judge-b`.

## Steps

1. **Inputs.** Write three files in a scratch dir (not in a repo):
   - `items.jsonl`: one `{"id": "...", "input": "..."}` per line.
   - `instructions.txt`: the generator system prompt, including the exact output format.
   - `rubric.txt` (optional): the judge system prompt. Judges answer
     `{"ok": true|false, "reason": "..."}`. If omitted, `instructions.txt` is reused, so write a separate rubric when the judge's job differs from the generator's.

2. **Gate and dry run.** `python3 <SKILL_DIR>/gen-validate.py --items ... --instructions ... --out <dir> --dry-run`.
   It checks args, runs `jev-gate route`, and prints the plan. No network, no key.
   Exit 4 means the data is restricted or the gate is unavailable. Stop and tell the
   operator. Never switch to an open or OpenCode model to get around it.

3. **Run.** Same command without `--dry-run`. The key comes from `LITELLM_GEN_KEY`, or
   the script reads Vault `secret/homelab/litellm/gen-validate#api_key` itself
   (`VAULT_ADDR`, default `http://127.0.0.1:8200`). Never print or echo the key. Judges
   use `max_tokens >= 300`, because gpt-oss is a reasoning model and returns empty content
   on small budgets. An empty or unparsable judge reply is `judge_error`, not a verdict.

4. **Spot-check.** Read `sample.jsonl` (random, seeded). Mark each item correct or
   wrong against the instructions. Read `disagree.jsonl` too. If the sample error rate
   is high, do not use `kept.jsonl`. Say so.

5. **Report.** Give `summary.md`: items, kept rate, judge agreement rate, judge_error
   and gen_failed counts, tokens, cost (LiteLLM header and priced, if you passed
   `--price-*-per-m`), and the spot-check result. Name the output dir.

## Outputs (in `--out`)

`generated.jsonl`, `judged.jsonl` (both verdicts, reasons, cost per item), `kept.jsonl`,
`disagree.jsonl`, `sample.jsonl`, `summary.json`, `summary.md`.
