---
name: helm-argocd
when: editing Helm charts, ArgoCD applications, Kubernetes manifests, or deploying to the k3s cluster
paths: */Code/helm*, */Code/argocd-apps*
---
- ArgoCD cannot see drift in fields a chart omits (e.g. `suspend: true` survived weeks while the app showed Synced). Set the field explicitly.
- Secrets arrive via ESO from Vault. Fix the Vault SOURCE, never the delivered k8s Secret — ESO overwrites it.
- No local-path PVCs. Use the NFS storage class. NFS is `all_squash`: run the pod as uid 65534, rsync without `-o -g`.
- To stop a workload managed by app-of-apps, disable selfHeal on the PARENT app first.
- Grafana Alloy container resources go under `alloy.resources`, not `controller.resources`.
- Infra changes go on a branch and a PR. Never push straight to main.
