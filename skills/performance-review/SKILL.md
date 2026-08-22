---
name: performance-review
description: Use when reviewing or optimizing performance of backend/streaming/data services — throughput, latency, allocations, blocking, batching, caching, backpressure, connection reuse, resource sizing, and honest benchmark methodology. Especially for Rust/async services, Kafka/stream relays, Redis-backed stores, and k8s workloads.
---

# Performance Review

Review for performance the way a systems engineer does: **measure first, attribute honestly, then optimize the proven bottleneck.** Most "slow" reports are measurement artifacts or the wrong layer. A number you can't attribute to a component is not evidence.

## Order of operations (do NOT skip)

1. **Measure before optimizing.** No change without a before-number from a representative workload. Profiling/metrics beat intuition every time.
2. **Attribute the bottleneck.** Is it the client (load generator), the network, the service's CPU, a lock, the datastore, or GC/allocator? A latency that exceeds the produce wall-time, or a throughput that matches a per-request round-trip, is a *client/methodology* artifact, not the service.
3. **Isolate the layer.** Read the service's own metrics (server-side latency histograms) separately from end-to-end client numbers. They answer different questions.
4. **Change one thing, re-measure.** Confirm the delta is real and caused by the change.

## Benchmark methodology (the traps)

- **Pipelining vs synchronous await.** A load generator that `await`s each request/send before the next measures round-trip latency, NOT service throughput. Fire concurrently (bounded in-flight), collect futures, await in bulk.
- **Measure end-to-end correctly.** The consumer/measurer must be running *before* the producer, read from the earliest offset, use a fresh consumer group, and stop on `received == expected` or an idle timeout — not a fixed window that truncates.
- **Same clock, same epoch.** Latency = `consume_time - produce_time` only if both use the same monotonic clock/epoch. A p50 > total wall-time means a clock or ordering bug.
- **Warm up.** Discard the first N (JIT/cache/connection warm-up) or report cold vs warm separately.
- **Percentiles, not averages.** p50/p95/p99/max via a histogram (HDR-style). Averages hide tail latency.
- **Representative data + scale sweep.** Vary the real dimensions (distinct keys/schemas, payload size, malformed rate) and report curves, not a single point.
- **Report what was NOT measured.** Silent caps, truncation, or a skipped scenario read as "covered" when they aren't. Say so.

## Hot-path checklist (per request/message)

- [ ] **No unnecessary allocation/clone in the hot path.** Reuse buffers; borrow, don't clone; avoid `to_string`/`format!` per message. Stream/parse with bounded buffers.
- [ ] **No blocking on an async runtime.** CPU-bound or blocking syscalls off the async threads (`spawn_blocking` / a dedicated pool). One blocking call stalls the whole executor.
- [ ] **Bounded work per item.** Enforce byte/depth/field/element limits *before* allocation (DoS + tail-latency guard). No unbounded recursion or unbounded collection growth.
- [ ] **Deterministic, cheap identity/lookup.** Hash/index lookups O(1); never a global scan/distance pass over all records on the hot path. Bounded buckets/inverted index.
- [ ] **Cache what repeats.** An LRU/decision cache keyed by a stable digest for repeated shapes; measure hit rate.

## Datastore + I/O

- [ ] **Connection reuse + pooling.** No connect-per-request. A multiplexed/managed connection with a bounded `response_timeout` and auto-reconnect (a connection that never reconnects after a blip is a latent outage).
- [ ] **Batch, don't N+1.** One pipelined/batched round-trip over M keys, not M round-trips. Watch loops that call the datastore per item (e.g. per-version, per-field reads).
- [ ] **Atomic multi-key ops server-side** (Lua/transaction) instead of read-modify-write races over the wire.
- [ ] **Right partition/parallelism.** A single-partition topic or single consumer serializes throughput; size partitions + consumers to the target rate. Transactional/exactly-once has real per-transaction overhead — batch records per transaction where correctness allows, and measure the ceiling.
- [ ] **Backpressure, not unbounded buffering.** Bounded channels/queues; shed or block, never OOM. A burst must not balloon end-to-end latency without bound.

## Concurrency

- [ ] **Lock scope minimal**; no lock held across `.await` or I/O. Prefer sharded/lock-free structures on the hot path (never a global `Mutex<HashMap>` per message).
- [ ] **Cancellation + timeouts** on every external call; a slow dependency must fail fast, not hang.
- [ ] **Idempotent + exactly-once cost understood** — know what the correctness guarantee costs in throughput, and that it's the *chosen* trade-off.

## Resource sizing (k8s / deploy)

- [ ] **Requests AND limits set** on every container (CPU + memory) — prevents noisy-neighbor and OOM-kill surprises; sized from measured usage, not guessed.
- [ ] **Placement** away from control-plane / latency-sensitive nodes; anti-affinity for co-located heavy workloads.
- [ ] **Startup + readiness cheap and honest** — readiness reflects real dependency health (datastore reachable), liveness doesn't flap.
- [ ] **Image + build** — release build, LTO/opt-level for the hot binary; avoid a debug build in prod. Layer/dep caching so iteration isn't 15 min.
- [ ] **Observability** — the service exposes latency histograms + throughput + saturation counters (bounded label cardinality — never per-id labels) so you can attribute in production, not just in a bench.

## Reporting

State the **bottleneck and its layer**, the **before/after numbers** with percentiles, the **scale curve**, what was **not** measured, and a **go/no-go** with the specific next optimization if any. Never report an unattributed number as a service limit.
