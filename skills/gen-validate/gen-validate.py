#!/usr/bin/env python3
"""gen-validate: cheap generator -> two independent judges -> keep agreed items -> sample for spot-check.

Bulk traffic goes ONLY through the homelab LiteLLM OpenAI-compatible API.
OpenCode Go is for coding agents; it is never used here.

Input : JSONL, one item per line: {"id": "...", "input": "..."} ("prompt" also accepted).
Task  : --instructions FILE (generator system prompt), --rubric FILE (judge system prompt).
Output: DIR/{generated,judged,kept,disagree,sample}.jsonl, summary.json, summary.md
Exit  : 0 ok, 2 bad args, 4 data not allowed (restricted/unknown tier), 5 no API key.
"""
import argparse
import concurrent.futures as cf
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "http://192.168.0.60:30400/v1"
DEFAULT_GEN = "deepseek/deepseek-chat"
DEFAULT_JUDGE_A = "deepseek/deepseek-chat"
DEFAULT_JUDGE_B = "groq/gpt-oss-120b"
MIN_JUDGE_TOKENS = 300  # gpt-oss is a reasoning model: small budgets return empty content


def die(code, msg):
    print(f"gen-validate: {msg}", file=sys.stderr)
    sys.exit(code)


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--items", required=True, help="JSONL input items")
    p.add_argument("--instructions", required=True, help="generator system prompt file")
    p.add_argument("--rubric", help="judge system prompt file (default: same as --instructions)")
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--generator", default=DEFAULT_GEN)
    p.add_argument("--judge-a", default=DEFAULT_JUDGE_A)
    p.add_argument("--judge-b", default=DEFAULT_JUDGE_B)
    p.add_argument("--base-url", default=os.environ.get("LITELLM_BASE_URL", DEFAULT_BASE))
    p.add_argument("--key-env", default="LITELLM_GEN_KEY")
    p.add_argument("--vault-path", default="secret/homelab/litellm/gen-validate")
    p.add_argument("--vault-field", default="api_key")
    p.add_argument("--max-tokens-gen", type=int, default=800)
    p.add_argument("--max-tokens-judge", type=int, default=MIN_JUDGE_TOKENS)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--sample", type=int, default=20, help="kept items to spot-check")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--price-in-per-m", type=float, default=0.0, help="USD per 1M input tokens (optional)")
    p.add_argument("--price-out-per-m", type=float, default=0.0, help="USD per 1M output tokens (optional)")
    p.add_argument("--dry-run", action="store_true", help="validate args, tier and plan; no network, no key")
    a = p.parse_args(argv)
    if a.judge_a == a.judge_b:
        die(2, "--judge-a and --judge-b must differ (independent judges)")
    for m in (a.generator, a.judge_a, a.judge_b):
        if m.startswith("opencode-go/") or "opencode" in a.base_url:
            die(2, f"refusing {m}: OpenCode Go is not for bulk data; use LiteLLM")
    if a.concurrency < 1 or a.sample < 0:
        die(2, "--concurrency must be >= 1 and --sample >= 0")
    a.max_tokens_judge = max(a.max_tokens_judge, MIN_JUDGE_TOKENS)
    return a


def load_items(path):
    items = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            inp = obj.get("input", obj.get("prompt"))
            if inp is None:
                die(2, f"items line {n}: missing 'input' (or 'prompt')")
            items.append({"id": str(obj.get("id", n)), "input": inp})
    if not items:
        die(2, "no items")
    return items


def jev_tier(paths, n_items):
    """Sensitivity gate. Missing or unparsable jev-gate output counts as restricted."""
    if not shutil.which("jev-gate"):
        return "restricted"
    cmd = ["jev-gate", "route", "--task", f"gen-validate {n_items} items"]
    for p in paths:
        cmd += ["--file", p]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        tier = json.loads(r.stdout).get("tier", "")
    except (ValueError, AttributeError):
        tier = ""
    return tier if tier in ("open", "standard", "restricted") else "restricted"


def api_key(env_name, vault_path, field):
    key = os.environ.get(env_name, "").strip()
    if key:
        return key
    env = dict(os.environ, VAULT_ADDR=os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200"))
    r = subprocess.run(["vault", "kv", "get", f"-field={field}", vault_path],
                       capture_output=True, text=True, env=env)
    key = r.stdout.strip()
    if r.returncode != 0 or not key:
        die(5, f"no API key: set {env_name} or make Vault {vault_path}#{field} readable (rc={r.returncode})")
    return key


def chat(base, key, model, system, user, max_tokens, retries=2):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }).encode()
    err = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            base.rstrip("/") + "/chat/completions", data=body, method="POST",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.load(resp)
                cost = float(resp.headers.get("x-litellm-response-cost") or 0)
            choice = (data.get("choices") or [{}])[0]
            usage = data.get("usage") or {}
            content = ((choice.get("message") or {}).get("content") or "").strip()
            return {"content": content, "in": usage.get("prompt_tokens", 0),
                    "out": usage.get("completion_tokens", 0), "cost": cost, "error": None}
        except urllib.error.HTTPError as e:
            err = f"http {e.code}"
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            break
        except Exception as e:  # network/timeout/parse: retry, then report the class only
            err = type(e).__name__
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            break
    return {"content": "", "in": 0, "out": 0, "cost": 0.0, "error": err}


def parse_verdict(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except ValueError:
        return None
    return obj if isinstance(obj.get("ok"), bool) else None


def judge(args, key, model, rubric, item, output):
    user = f"INPUT:\n{item['input']}\n\nGENERATED OUTPUT:\n{output}"
    res = chat(args.base_url, key, model, rubric, user, args.max_tokens_judge)
    verdict = parse_verdict(res["content"]) if not res["error"] else None
    status = "error" if res["error"] or verdict is None else "ok"
    if res["error"]:
        reason = res["error"]
    elif verdict is None:
        reason = "empty or unparsable judge reply"  # counts as a failure, not a verdict
    else:
        reason = verdict.get("reason", "")
    return {"model": model, "status": status, "ok": verdict["ok"] if status == "ok" else None,
            "reason": str(reason)[:300], "in": res["in"], "out": res["out"], "cost": res["cost"]}


def run_item(args, key, rubric, gen_sys, item):
    gen = chat(args.base_url, key, args.generator, gen_sys, item["input"], args.max_tokens_gen)
    if gen["error"] or not gen["content"]:
        return {"id": item["id"], "input": item["input"], "output": None, "stage": "gen_failed",
                "gen_error": gen["error"] or "empty", "judges": [], "gen_in": gen["in"],
                "gen_out": gen["out"], "gen_cost": gen["cost"]}
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(judge, args, key, args.judge_a, rubric, item, gen["content"])
        fb = pool.submit(judge, args, key, args.judge_b, rubric, item, gen["content"])
        ja, jb = fa.result(), fb.result()
    if ja["status"] != "ok" or jb["status"] != "ok":
        stage = "judge_error"
    elif ja["ok"] and jb["ok"]:
        stage = "kept"
    elif not ja["ok"] and not jb["ok"]:
        stage = "rejected"
    else:
        stage = "disagree"
    return {"id": item["id"], "input": item["input"], "output": gen["content"], "stage": stage,
            "judges": [ja, jb], "gen_in": gen["in"], "gen_out": gen["out"], "gen_cost": gen["cost"]}


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def summarize(args, results, tier):
    n = len(results)
    count = lambda s: sum(1 for r in results if r["stage"] == s)
    valid_pairs = [r for r in results if r["stage"] in ("kept", "rejected", "disagree")]
    agree = sum(1 for r in valid_pairs if r["judges"][0]["ok"] == r["judges"][1]["ok"])
    tok_in = sum(r["gen_in"] + sum(j["in"] for j in r["judges"]) for r in results)
    tok_out = sum(r["gen_out"] + sum(j["out"] for j in r["judges"]) for r in results)
    header_cost = sum(r["gen_cost"] + sum(j["cost"] for j in r["judges"]) for r in results)
    priced = (tok_in * args.price_in_per_m + tok_out * args.price_out_per_m) / 1e6
    return {
        "tier": tier, "generator": args.generator, "judges": [args.judge_a, args.judge_b],
        "items": n, "gen_failed": count("gen_failed"), "judge_error": count("judge_error"),
        "kept": count("kept"), "rejected": count("rejected"), "disagree": count("disagree"),
        "kept_rate": round(count("kept") / n, 4) if n else 0.0,
        "judge_agreement_rate": round(agree / len(valid_pairs), 4) if valid_pairs else None,
        "tokens_in": tok_in, "tokens_out": tok_out,
        "cost_usd_litellm_header": round(header_cost, 6),
        "cost_usd_priced": round(priced, 6) if (args.price_in_per_m or args.price_out_per_m) else None,
    }


def write_summary(out, summary, sample_n):
    with open(os.path.join(out, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    lines = ["# gen-validate summary", ""]
    lines += [f"- {k}: {v}" for k, v in summary.items()]
    lines += ["", f"Spot-check: {sample_n} kept items in sample.jsonl. Claude reads them and reports "
              "how many are wrong, and whether the judges' agreement is trustworthy."]
    with open(os.path.join(out, "summary.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")


def main(argv):
    args = parse_args(argv)
    with open(args.instructions, encoding="utf-8") as fh:
        gen_sys = fh.read()
    rubric = gen_sys
    if args.rubric:
        with open(args.rubric, encoding="utf-8") as fh:
            rubric = fh.read()
    items = load_items(args.items)
    tier = jev_tier([args.items, args.instructions], len(items))
    if tier == "restricted":
        die(4, "jev-gate tier is restricted (or jev-gate unavailable): refusing to send data to "
               "China-hosted or open endpoints")
    plan = {"items": len(items), "tier": tier, "base_url": args.base_url, "generator": args.generator,
            "judges": [args.judge_a, args.judge_b], "concurrency": args.concurrency,
            "max_tokens_judge": args.max_tokens_judge}
    if args.dry_run:
        print("dry-run plan:", json.dumps(plan, indent=2))
        return 0

    key = api_key(args.key_env, args.vault_path, args.vault_field)
    os.makedirs(args.out, exist_ok=True)
    with cf.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(lambda it: run_item(args, key, rubric, gen_sys, it), items))

    write_jsonl(os.path.join(args.out, "generated.jsonl"),
                [{"id": r["id"], "input": r["input"], "output": r["output"], "stage": r["stage"]} for r in results])
    write_jsonl(os.path.join(args.out, "judged.jsonl"), results)
    kept = [r for r in results if r["stage"] == "kept"]
    write_jsonl(os.path.join(args.out, "kept.jsonl"),
                [{"id": r["id"], "input": r["input"], "output": r["output"]} for r in kept])
    write_jsonl(os.path.join(args.out, "disagree.jsonl"),
                [r for r in results if r["stage"] == "disagree"])
    sample = random.Random(args.seed).sample(kept, min(args.sample, len(kept)))
    write_jsonl(os.path.join(args.out, "sample.jsonl"), sample)
    summary = summarize(args, results, tier)
    write_summary(args.out, summary, len(sample))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
