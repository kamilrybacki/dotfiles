#!/usr/bin/env node
// humanify-text scanner. Reads a text/markdown file and reports AI-writing
// tells by category, with line samples, so an editor knows exactly what to
// rewrite. It flags problems; it does NOT auto-edit (rewrites need judgement).
//
// Usage:   node scan.mjs <file> [--samples N]
// Exit:    1 if any HARD category (dashes / forbidden transitions / AI vocab)
//          has a hit, else 0. Soft categories never fail the run; they inform.
//
// Design notes:
// - Code fences (``` ... ```) and inline `code` are stripped before scanning
//   so JSON/latency/identifiers never trip a rule.
// - Metrics compare against the AUTHOR'S OWN corpus, not a universal threshold.
//   Pass older posts too and eyeball the drift; there is no "human" cutoff.

import { readFileSync } from "node:fs";

const args = process.argv.slice(2);
const file = args.find((a) => !a.startsWith("--"));
const samples = Number((args.find((a) => a.startsWith("--samples=")) || "=3").split("=")[1]) || 3;
if (!file) {
  console.error("usage: node scan.mjs <file> [--samples=N]");
  process.exit(2);
}

const raw = readFileSync(file, "utf8");

// Strip fenced code blocks and inline code so we only lint prose.
const prose = raw
  .replace(/```[\s\S]*?```/g, (m) => m.replace(/[^\n]/g, " "))
  .replace(/`[^`\n]*`/g, (m) => m.replace(/[^\n]/g, " "));

const lines = prose.split("\n");

// category: [label, hardness, regex, note]
const HARD = "HARD";
const SOFT = "soft";

const AI_VOCAB = [
  "delve","tapestry","landscape","pivotal","underscore","testament","intricate",
  "intricacies","meticulous","meticulously","nuanced","multifaceted","crucial",
  "robust","seamless","seamlessly","foster","enhance","showcase","leverage",
  "garner","bolster","bolstered","interplay","realm","embark","spearhead",
  "vibrant","holistic","cutting-edge","game-changer","resonate","illuminate",
];
const TRANSITIONS = [
  "Moreover","Furthermore","However","Therefore","Additionally","Consequently",
  "Thus","Notably","Nonetheless","Nevertheless","Subsequently","Hence","Indeed",
  "In conclusion","In summary","To summarize","Ultimately","Essentially",
  "Firstly","Specifically","Importantly","Similarly","As a result","Alternatively",
  "On the other hand","In contrast","Despite","Although","Even though","In order to",
];

const rules = [
  ["em/en dashes", HARD, /[—–]/g, "rephrase; never just swap to a comma"],
  ["forbidden transitions", HARD, new RegExp("(^|[.\\s])(" + TRANSITIONS.join("|") + ")\\b", "g"),
    "delete the connector; adjacency usually carries the logic"],
  ["AI vocabulary", HARD, new RegExp("\\b(" + AI_VOCAB.join("|") + ")\\b", "gi"),
    "use the project's own nouns/verbs, not rarer synonyms"],
  ["negative parallelism", SOFT, /\bnot just\b|\bnot only\b|\bit'?s not (a|an|about|just)\b/gi,
    "state what it IS; drop the dramatic negation setup"],
  // "wasn't the X. It was Y" / "isn't the X, it's Y" — copula negation then reveal,
  // often split across two sentences. Anchored to article+noun so passives
  // ("isn't shown by the test. That regime is …") don't false-trip.
  ["copula negation reveal", SOFT,
    /\b([Ww]asn't|[Ii]sn't|[Ww]eren't|[Aa]ren't)\s+(the|a|an|my|your|its|his|her|their|our|about|just|only)\b[^.!?\n]{0,45}([.!?]\s+(It|That)\s+(was|is|'s)\b|,\s+(it's|that's)\b)/g,
    "state it directly; don't set up 'wasn't X' then reveal 'It was Y'"],
  ["participial benefit tail", SOFT,
    /,\s+(ensuring|highlighting|underscoring|showcasing|enabling|allowing|reflecting|symbolizing|emphasizing|fostering)\b/gi,
    "name actor+verb+mechanism in a new sentence; delete if it only praises"],
  ["false range 'from X to Y'", SOFT, /\bfrom\s+\w+\s+to\s+\w+\b/gi,
    "list the two real things and note they differ"],
  // Universalizer wraps the sentence: "Whether X or Y, <conclusion>". Anchored to a
  // leading boundary so indirect questions ("the question was whether X or Y") don't trip.
  ["'whether X or Y' universalizer", SOFT, /(^|[.!?]\s+|,\s+)[Ww]hether\b[^.?!\n]{0,80}\bor\b/g,
    "make the precise point for the real audience; drop the catch-all inclusiveness"],
  ["importance inflation", SOFT,
    /\b(it is (crucial|important) to note|worth noting|at its core|this is where|it is worth|plays a (vital|key|crucial) role|serves as a testament|paves the way|unlocks)\b/gi,
    "delete the label; state the fact and let the reader judge"],
  ["staged question+answer", SOFT, /\b(The (result|outcome|upshot|point|answer)\?)\s/g,
    "make the point directly, no rhetorical setup"],
  ["metadiscourse opener", SOFT,
    /(^|\n)\s*(In today'?s|In an era|In the world of|When it comes to|In the realm of)\b/gi,
    "cut the throat-clearing; open on the concrete fact"],
  ["nominalization 'the X of'", SOFT,
    /\bthe (implementation|utilization|optimization|facilitation|validation|integration|reduction|application) of\b/gi,
    "turn back into a verb: 'validates', 'reduces', 'integrates'"],
  ["restatement marker", SOFT, /\b(in other words|to put it simply|simply put|that is to say)\b/gi,
    "keep the clearer sentence; delete the restatement"],
  ["hedge density", SOFT, /\b(seem|seems|seemed|appears?|looks like|arguably|to some extent|generally speaking)\b/gi,
    "keep hedges only on genuine judgements; thin clusters"],
];

let hardHits = 0;
const report = [];
for (const [label, hardness, re, note] of rules) {
  const hits = [];
  lines.forEach((ln, i) => {
    const m = ln.match(re);
    if (m) hits.push({ line: i + 1, count: m.length, text: ln.trim().slice(0, 100) });
  });
  const total = hits.reduce((s, h) => s + h.count, 0);
  if (hardness === HARD && total > 0) hardHits += total;
  report.push({ label, hardness, total, hits, note });
}

// ---- lightweight stylometry (drift signals, compare vs author's own posts) ----
const words = prose.split(/\s+/).filter(Boolean).length || 1;
const per1k = (n) => (n * 1000 / words).toFixed(1);
const sentences = prose
  .replace(/\n+/g, " ")
  .split(/(?<=[.!?])\s+/)
  .map((s) => s.trim())
  .filter((s) => s.split(/\s+/).length > 1);
const lens = sentences.map((s) => s.split(/\s+/).length);
const mean = lens.reduce((a, b) => a + b, 0) / (lens.length || 1);
const sd = Math.sqrt(lens.reduce((a, b) => a + (b - mean) ** 2, 0) / (lens.length || 1));
const cv = mean ? (sd / mean).toFixed(2) : "0";
const emdash = (prose.match(/[—–]/g) || []).length;

// ---- print ----
const C = { red: "\x1b[31m", yellow: "\x1b[33m", green: "\x1b[32m", dim: "\x1b[2m", off: "\x1b[0m" };
console.log(`\nhumanify-text scan  ${file}  (${words} prose words, ${sentences.length} sentences)\n`);
for (const r of report) {
  const tag = r.hardness === HARD ? (r.total ? C.red + "HARD" : C.green + "hard") : C.yellow + "soft";
  const head = `${tag}${C.off}  ${r.label.padEnd(26)} ${r.total}`;
  console.log(head);
  if (r.total) {
    console.log(`      ${C.dim}fix: ${r.note}${C.off}`);
    for (const h of r.hits.slice(0, samples)) {
      console.log(`      ${C.dim}L${h.line}:${C.off} ${h.text}`);
    }
    if (r.hits.length > samples) console.log(`      ${C.dim}… ${r.hits.length - samples} more line(s)${C.off}`);
  }
}
console.log(`\nmetrics (compare vs your OWN older posts, not a universal threshold):`);
console.log(`  sentence-length: mean ${mean.toFixed(1)}, sd ${sd.toFixed(1)}, CV ${cv}`);
console.log(`  em/en dashes per 1k words: ${per1k(emdash)}  (raw ${emdash})`);
console.log("");

if (hardHits > 0) {
  console.log(`${C.red}FAIL${C.off}: ${hardHits} hard-category hit(s). Rewrite before shipping.\n`);
  process.exit(1);
} else {
  console.log(`${C.green}PASS${C.off}: no hard-category tells. Review soft categories by hand.\n`);
  process.exit(0);
}
