---
root: true
targets: ["claudecode", "codexcli", "pi"]
description: "compool: job broker for compute, data generation and fine-tuning runs (Kaggle/Modal), reached via Splicedock compool__* tools"
globs: ["**/*"]
---

## Compute jobs: compool

`compool` is the homelab job broker for heavy compute. It runs jobs on Kaggle and
Modal and is reachable through Splicedock as the `compool__*` tools (check
`compool__*` before shelling out or running training locally).

- **Computation and data generation → CPU preferred.** Batch computation, dataset
  generation, preprocessing and evaluation sweeps go to a CPU run. Pick GPU only when
  the workload actually needs it.
- **Fine-tuning models → GPU.** Training and fine-tuning runs go to a GPU run.
- **Cost:** Kaggle runs are free. Modal runs are paid (hard stop at 27 USD, workspace
  limit 29 USD). Prefer the free backend; ask the operator before ANY paid Modal run,
  and never start one on your own.
- **Habits:** keep the job small and reproducible (bundle in, results out), check the
  run status instead of polling in a loop, and never put secrets in a job bundle.
