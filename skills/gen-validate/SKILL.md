---
name: gen-validate
description: Bulk labelled-data generation with independent-judge validation. A cheap generator labels each item, two judges from different vendors check every label, only items both accept are kept, and Claude spot-checks a random sample. Reports agreement rate and cost. Runs ONLY through the homelab LiteLLM API, never OpenCode Go, and refuses restricted data. Use for generating or validating training or eval labels in bulk.
user-invocable: true
---

# gen-validate

Bulk traffic goes through the homelab LiteLLM OpenAI-compatible API. Set
`LITELLM_BASE_URL` to its LAN URL (the script default is the homelab address). The
OpenCode Go subscription is for interactive coding only, and the script refuses it.

Pipeline: generator labels each item -> sensitivity check -> judge A and judge B each
check the label -> keep items both accept -> sample kept items for a Claude spot-check
-> report.

Defaults: generator `deepseek/deepseek-chat`; judges `deepseek/deepseek-chat` and
`groq/gpt-oss-120b` (different vendors). Override with `--generator`, `--judge-a`, `--judge-b`.

## Steps

1. **Inputs.** Write three files in a scratch dir (not in a repo):
   - `items.jsonl`: one `{"id": "...", "input": "..."}` per line. `input` must be a string.
   - `instructions.txt`: the generator system prompt, including the exact output format.
   - `rubric.txt` (optional): the judge system prompt. Judges answer
     `{"ok": true|false, "reason": "..."}`. If omitted, `instructions.txt` is reused.

2. **Gate and dry run.** `python3 <SKILL_DIR>/gen-validate.py --items ... --instructions ... --out <dir> --dry-run`.
   It classifies the DECODED JSON strings (keys and ids included), the instructions, and
   the rubric with the deterministic rules in `sensitivity.py`. No network, no key.
   - Any hit (infra, secret or network paths; private keys, tokens, or 192.168.x /
     10.x addresses in the data) exits 4 and refuses the run. Restricted data never goes
     to open or China-hosted endpoints. There is no override flag. Stop and tell the
     operator. Never move the data to another model to get around the hit.
   - Generated outputs are classified before the judges see them. A hit stores the item as
     `blocked_restricted` and sends nothing to the judges.

3. **Run.** Same command without `--dry-run`. The key comes from `LITELLM_GEN_KEY`, or
   the script reads Vault `secret/homelab/litellm/gen-validate#api_key` itself
   (`VAULT_ADDR`, default `http://127.0.0.1:8200`). Never print or echo the key. Judges
   use `max_tokens >= 300`, because gpt-oss is a reasoning model and returns empty content
   on small budgets. An empty or unparsable judge reply is `judge_error`, not a verdict.

4. **Spot-check.** Read `sample.jsonl` (random, seeded). Mark each item correct or
   wrong against the instructions. Read `disagree.jsonl` too. If the sample error rate
   is high, do not use `kept.jsonl`. Say so.

5. **Report.** Give `summary.md`: items, kept rate, judge agreement rate, judge_error,
   gen_failed and blocked_restricted counts, tokens, cost (LiteLLM header, and priced if
   you passed `--price-*-per-m`), and the spot-check result. Name the output dir.

## Outputs (in `--out`)

`generated.jsonl`, `judged.jsonl` (both verdicts, reasons, cost per item), `kept.jsonl`,
`disagree.jsonl`, `sample.jsonl`, `summary.json`, `summary.md`.
