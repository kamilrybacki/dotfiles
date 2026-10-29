---
name: grafana-alerting
when: writing or debugging Grafana alert rules, PromQL/LogQL queries, dashboards or Loki/Prometheus metrics
paths: */Code/grafana-dashboards*
---
- Alert rules: use `instant: true`, not range + reduce(last). Deleted series otherwise keep alerting for 10m and race `for:`.
- `up == 0` matches ~100 generic pod-discovery targets. Scope it by job.
- Staleness of weekly cron jobs: compare `last_schedule` with `last_successful`, not wall-clock age.
- PromQL precedence: `>` binds tighter than `unless`.
- Prometheus has no scrape_configs. Alloy scrapes and remote_writes, and its curate_* keep-lists drop unlisted metrics.
