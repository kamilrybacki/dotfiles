---
name: vault-secrets
when: reading, writing, rotating or wiring secrets, API keys, tokens, Vault paths or External Secrets
---
- Vault layout: `secret/homelab/<issuer>/<credential>`. k8s delivery is ESO ExternalSecrets; sops is retired.
- Never print a secret value into the transcript or a log. Pipe it straight into its consumer.
- Patch the Vault source, not the delivered Secret; ESO re-syncs over hand edits.
- The cellarette vault-mcp token expires about monthly. A 403 there usually means token expiry, not a missing policy.
- Rotating a credential means updating every consumer. Check ESO SecretSynced status after the change.
