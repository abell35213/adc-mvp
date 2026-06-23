# Deployment Rollback Runbook

Use this runbook when staging smoke tests or production health checks fail after promoting a new deployment.

## Inputs
- `deploy_version`: Version identifier emitted by CI/CD (defaults to commit SHA).
- `last_known_good_version`: Most recent healthy release.

## Trigger Conditions
- `post-deploy-health-checks` job fails in `.github/workflows/deploy-promotion.yml`.
- Incident commander declares rollback in active incident channel.

## Immediate Actions
1. Pause additional deploys by disabling automatic triggers or applying a deployment freeze.
2. Announce rollback start in incident timeline and include `deploy_version`.
3. Execute rollback hook:

```bash
./scripts/deploy_hooks.sh rollback <deploy_version>
```

4. Re-deploy `last_known_good_version` using normal production hook:

```bash
./scripts/deploy_hooks.sh production <last_known_good_version>
```

5. Re-run health checks:

```bash
./scripts/deploy_hooks.sh health-check <last_known_good_version>
```

## Verification Checklist
- Public health endpoint reports healthy.
- Key product flows pass synthetic checks.
- Error-rate and latency dashboards return to baseline.
- Incident timeline includes rollback command outputs.

## Automation Hooks
- Hook script: `scripts/deploy_hooks.sh`.
- Stages currently wired: `staging`, `smoke`, `production`, `health-check`, `rollback`.
- The hook drives Kubernetes rollouts via `kubectl` and is config-driven so the
  push-to-main pipeline stays green where no cluster is reachable:
  - Real execution requires `DEPLOY_ENABLED=1` (set via the GitHub Environment
    for `staging` / `production`). When unset, every stage logs a skip and exits
    `0` instead of failing.
  - `staging` / `production` run `kubectl set image` + `kubectl rollout status`
    for the backend and worker deployments, pinning the image to `deploy_version`.
  - `smoke` / `health-check` poll `DEPLOY_STAGING_HEALTH_URL` /
    `DEPLOY_PRODUCTION_HEALTH_URL` (the `/health/ready` endpoint) with bounded
    retries.
  - `rollback` runs `kubectl rollout undo` + `kubectl rollout status` for the
    backend and worker deployments.
- Deployment targets default to the `infra/production` manifests (namespace
  `adc`, deployments `adc-backend` / `adc-worker`) and are overridable via the
  `DEPLOY_K8S_*` / `DEPLOY_IMAGE_REPOSITORY` environment variables documented in
  the script header.

## Incident Correlation
- Always include `deploy_version` in:
  - GitHub Actions logs.
  - Backend startup logs.
  - Frontend UI version badge.
