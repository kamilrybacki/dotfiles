---
name: humanify-text
description: Humanify / humanize prose by scanning text for AI-writing tells and rewriting them out. Use when asked to remove AI-isms, de-slop, humanize, de-AI, or make writing sound human. Covers em-dashes, forbidden transitions, AI vocabulary, negative parallelism, rule-of-three, participial tails, importance inflation, nominalizations.
---

# humanify-text

Edit prose so it reads like a person wrote it, not a model. `scan.mjs` is a
**first-pass net, not the judge.** It catches literal surface forms of the
tells, but these tells are *semantic moves*, not strings. A green scan does
not mean the prose is clean, and a red hit is not automatically a defect.
You still have to **read for the move** (section below). The script flags
candidates; you decide, using meaning, and rewrite by hand.

Grounded in the joint research `jr-aitells-281146` (Claude × Hermes):
Wikipedia "Signs of AI writing" + stylometry/detector papers (GPTZero,
GLTR, DetectGPT, Fast-DetectGPT, Binoculars, Ghostbuster, HC3, Kobak
excess-vocabulary) + Jurić, "Common Sentence Structures in AI Writing"
(stryng.io, 2026): from-to ranges, whether-or universalizers, not-just-but
contrasts, participle tails, rule-of-three, hedging. Report lives at
`~/Code/kamilrybacki.github.io/joint-research-jr-aitells-281146.md`.

## Core principle

The real tell is **probability-regular, repeatedly-packaged prose**: the
same chassis reused paragraph after paragraph (claim, dash qualification,
three-item list, `-ing` consequence tail), detached from concrete evidence.
No single word or em-dash proves anything. Fix the packaging, not just the
vocabulary. Detectors key on token predictability, log-rank, and curvature,
so the manual proxy is: cut generic, templated, evidence-free passages and
put the author's own numbers, commands, failures, and decisions back in.

## Read for the move (semantics, not string-matching)

A regex matches characters. The tell is a **rhetorical intent**, and the
same intent wears many surface forms. `scan.mjs` will always both miss and
over-fire, so after every scan you read the prose yourself and judge the
*move each sentence makes*, not whether a pattern literally matched.

Two failure modes the scanner cannot fix on its own:

- **Miss (paraphrase / split).** "The clever bit **wasn't** the model. **It
  was** the placement." is the "not X, it's Y" move split across two
  sentences with `wasn't`/`It was` — no `not just` string, so a naive regex
  slides past it. Same move, also invisible to regex: "Less the model than
  the gate around it", "The model matters less than you'd think; the tiers
  do the work". When you read a sentence that **sets up a negation and then
  delivers the real answer**, that is the tell, whatever words carry it.
- **False positive (legitimate use).** "The real question was **whether** a
  small model pulls its weight, **or** just adds latency" is an indirect
  question, not the "Whether X or Y, [everyone wins]" universalizer. "A
  replay, not corrupted data" is a precise factual contrast, not dramatic
  reframing. A pattern that matched but carries real, specific meaning
  **stays**.

For each flagged (or suspected) structure, ask what it is *doing*:

| Structure | Its semantic move (the actual tell) | Legitimate version to keep |
|---|---|---|
| not X, it's Y / wasn't X. It was Y | negation-then-reveal for false drama; the reveal is usually vague | a precise either/or where both sides carry specific meaning |
| from X to Y | fake comprehensiveness: two poles implying everything between is covered | a real, meaningful span ("from cold start to steady state") |
| whether X or Y | universalizer: dodges committing to one audience or claim | an indirect question, or a genuine two-branch condition |
| rule of three | three parallel items chosen for rhythm, not because there are three | a list that genuinely has three members |
| participial `-ing` tail | tacked-on clause that praises or restates without new mechanism | a tail that adds a real, distinct action or consequence |
| importance inflation | telling the reader something matters instead of showing it | naming stakes that are concrete and load-bearing |
| hedging | blanket caution to avoid any falsifiable claim | a hedge on a genuine, stated uncertainty |

The unifying question when reading any candidate: **does this sentence add
specific information, or does it only add shape?** Shape without information
is the tell, regardless of which template produced it. Information in a
templated shape can stay.

## Run (agent path)

Prereq: Node (any recent version; no packages needed).

Scan a file:

```bash
node ~/.claude/skills/humanify-text/scan.mjs <file.md>
```

Show more line samples per category:

```bash
node ~/.claude/skills/humanify-text/scan.mjs <file.md> --samples=6
```

Output: three HARD categories (dashes / forbidden transitions / AI vocab)
that fail the run, then soft categories that inform, then stylometry
metrics. Exit 1 while any hard hit remains, 0 when clean. Code fences and
inline `code` are stripped before scanning, so JSON, latencies, and
identifiers never trip a rule.

Verified run on a clean post:

```
$ node ~/.claude/skills/humanify-text/scan.mjs src/content/articles/braid.md
hard  em/en dashes               0
hard  forbidden transitions      0
hard  AI vocabulary              0
soft  hedge density              7
metrics: sentence-length mean 18.5, sd 11.8, CV 0.64 ; em/en dashes per 1k 0.0
PASS: no hard-category tells. Review soft categories by hand.
```

Verified run on an AI-slop sample (fails as it should):

```
$ node ~/.claude/skills/humanify-text/scan.mjs slop-sample.md
HARD  em/en dashes               1
HARD  forbidden transitions      2
HARD  AI vocabulary              8
FAIL: 11 hard-category hit(s). Rewrite before shipping.
```

## Workflow

1. **Scan (coverage floor).** Run the driver for the literal hits. This is
   the net, not the verdict.
2. **Semantic read (the real pass, mandatory).** Read the whole text
   paragraph by paragraph. For every sentence ask: *what move is it making,
   and does it add information or only shape?* Flag the negation-reveals,
   fake-comprehensive ranges, hollow tricolons, and praise-tails the regex
   missed because they were paraphrased or split across sentences. This step
   is where most real edits come from; the scan only seeds it.
3. **Judge each scan hit by meaning.** A matched pattern that carries
   specific, load-bearing information stays (indirect "whether", a precise
   "A, not B" factual contrast). Do not delete a hit just because it matched.
4. **Rewrite per category** (table below). Never mass-swap; each hit is a
   sentence to re-think. Replace shape with information: name the actor,
   verb, mechanism, or number.
5. **Re-scan** until hard categories are 0, then read once more. A clean
   scan with templated, evidence-free prose is still not done.
6. **Verify meaning + numbers intact.** Diff against the original. Every
   measured number, table cell, and code block stays byte-for-byte.

## Rewrite guide (before → after)

| Tell | Before | After |
|---|---|---|
| em/en dash | `A misroute is a replay — not corrupted data.` | `A misroute is a replay, not corrupted data.` (rephrase, don't just comma-swap a habitual dash) |
| forbidden transition | `Moreover, the cache cuts latency.` | `The cache also cuts latency.` (or delete the connector) |
| AI vocabulary | `a robust, seamless framework` | `a framework that survived 421 requests with no OOM kills` |
| negative parallelism | `It's not just a router; it's a governance layer.` | `Braid routes events. A separate gate controls side effects.` |
| rule-of-three | `scalable, robust, and maintainable` | pick the one that carries weight, or give one measurement |
| participial tail | `retries writes, ensuring delivery.` | `retries writes. Consumers dedupe by decision ID.` |
| false range | `From alerts to webhooks, it handles everything.` | `It accepts Grafana alerts and GitHub webhooks. Each needs its own predicates.` |
| whether-or universalizer | `Whether the payload is an email or an alert, the same engine works.` | `The engine accepts both shapes. Their catalogs and tests differ.` |
| importance inflation | `It is crucial to note that replay needs stable IDs.` | `Replay needs stable origin and decision IDs.` |
| staged question | `The result? A faster router.` | `The predicate path is deterministic; the model sees only the tail.` |
| nominalization | `the implementation of validation enables the reduction of failures` | `validation rejects malformed route sets before delivery` |
| anthropomorphism | `Braid understands the event.` | `the model proposes labels from a fixed catalog` |
| recap conclusion | `In summary, small models are the future.` | end on the actual result: `The 26M model kept 0.875 in-distribution; its JAX path stayed slow.` |

## The one rule that matters most

Do **not** fake humanity. No injected typos, no random rare synonyms, no
invented anecdotes, no arbitrary sentence-length noise. That shifts
detector signals without improving the text, and it can make the writing
worse. Humanize by **adding real fingerprints** instead:

- exact version / runtime (`ollama Q4`, `Transformers`, host CPU);
- a measured number with its conditions (`0.43 s p50 on the same box`);
- one approach that failed and why;
- an unresolved edge case you actually hit;
- a first-person decision where authorship matters (`I kept Qwen because
  the merged artifact was the serving path I could reproduce`).

## Preserve, don't strip

- The author's voice and deliberate hedges (`seems`, `looks like`) on
  genuine judgements. The scanner flags hedge *density*; thin clusters,
  keep the honest ones.
- Code blocks, tables, data, and every measured number, verbatim.

## Measurement (drift, not a verdict)

There is no universal "human" threshold. Compare the draft against the
**author's own** older posts in the same genre. The scanner prints
sentence-length mean/sd/CV and em-dash-per-1k. Lower CV than the author's
usual = flat, templated rhythm. For deeper audits: participial-tail and
nominalization counts per 1k, punctuation per 1k, MTLD/HD-D lexical
diversity (not raw type-token ratio, which length-biases), and any 2–5
word glue phrase that recurs across a short piece.

## Self-scoring checklist

Ship only when:

- [ ] `scan.mjs` exits 0 (zero dashes, zero forbidden transitions, zero AI vocab)
- [ ] you did the semantic read, not just the scan: every negation-reveal, fake range, hollow tricolon, and praise-tail caught even where no regex fired
- [ ] every sentence adds information, not only shape
- [ ] no paragraph reuses the same chassis as the one before it
- [ ] every "it's important/crucial" and "at its core" is gone; facts stand alone
- [ ] participial `-ing` tails that only praise the prior clause are cut
- [ ] rule-of-three lists trimmed to what carries weight
- [ ] the piece ends on a result, not a recap of itself
- [ ] at least one real fingerprint added per major claim (number, version, failure, decision)
- [ ] deliberate hedges kept; code, tables, and numbers unchanged
- [ ] sentence-length CV is in the author's normal range (not mechanically flattened)

## Gotchas

- The scanner strips fenced/inline code first. If a tell hides inside a
  code comment on purpose, it won't be seen — that's intended.
- `--samples=N` controls lines shown per category, not detection. Every
  hit is counted regardless.
- Soft categories are advisory. `hedge density` firing is normal on a post
  with honest judgement calls; do not zero it out reflexively.
- Hard-category regexes match sentence-initial transitions and whole-word
  vocab only, to avoid false positives on words like "however" inside a
  quote or "foster" as a name. Skim the samples before deleting.

## Files

- `scan.mjs` — the scanner/driver (this directory).
- Doctrine source: `joint-research-jr-aitells-281146.md` in the blog repo.
