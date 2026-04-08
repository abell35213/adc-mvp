# Playbook: Secrets Recovery

## Scope

Recover access to runtime secrets required by backend/worker workloads:

- Database connection string.
- Redis URL.
- Object storage bucket identifiers and credentials.
- JWT/OTP provider credentials.

## Trigger conditions

- Secrets manager outage or region failure.
- Secret deletion/corruption.
- Incorrect version stage promoted to production.

## Procedure

1. Identify impacted secret IDs and workloads failing startup or runtime auth.
2. Recover latest known-good secret versions from replicated region or audit history.
3. Re-attach correct version stage (for example, `AWSCURRENT`) to known-good payload.
4. Reconcile mandatory key set against deployment requirements.
5. Roll backend and worker pods to refresh in-memory credentials.
6. Validate health endpoints and authentication-dependent flows.

## Validation

- No startup failures due to missing env/secret values.
- DB/Redis/storage dependent endpoints pass smoke tests.
- RTO <= 45 minutes.

## Hardening assumptions

- Secret values are recoverable from version history/audit logs.
- At least one secondary operator has break-glass access.
- Secret catalog is documented and reviewed quarterly.
