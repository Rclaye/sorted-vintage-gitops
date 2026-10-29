# sorted-vintage-gitops

Desired state for the **Sorted Vintage** platform. Argo CD syncs this repository to the cluster; nothing else writes workloads to it ([ADR-0002](https://github.com/Rclaye/sorted-vintage-infra/blob/main/docs/adr/0002-git-is-the-only-path-to-the-cluster.md)).

## Layout (from Sprint 1)

```text
bootstrap/                     Argo CD root application (app of apps)
platform/<component>/          Shared add-ons: ingress, monitoring, logging, tracing, data stores
services/<name>/base/          Service manifests
services/<name>/overlays/dev   Synced automatically
services/<name>/overlays/prod  Changed only by reviewed pull request
```

## Who changes what

| Path | Changed by |
| --- | --- |
| `services/*/overlays/dev` image tags | GitHub Actions |
| `services/*/overlays/prod` | Promotion pull requests |
| Everything else | The engineer, by pull request |
