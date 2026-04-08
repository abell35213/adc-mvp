# Restore Validation Checklist (Non-Prod Drill)

## Drill metadata

- Date/time (UTC):
- Incident commander:
- Participants:
- Simulated scenario:
- Target system(s):
- Declared outage start:
- Service restored timestamp:

## Validation gates

### 1) PostgreSQL restore validation

- [ ] Restore instance created from latest full backup snapshot.
- [ ] WAL replay / PITR applied to target timestamp.
- [ ] `alembic current` equals expected head revision.
- [ ] CRUD smoke test passes for incidents and artifacts tables.
- [ ] Background worker DB tasks complete with no retry storm.
- [ ] Measured DB restore RPO <= 15 minutes.
- [ ] Measured DB restore RTO <= 60 minutes.

### 2) Object storage validation

- [ ] Bucket versioning confirmed enabled.
- [ ] Lifecycle policy attached and matches retention standard.
- [ ] Random sample restore from non-current object version succeeds.
- [ ] Checksums/hash metadata match expected values for sample files.
- [ ] Export job can include restored objects.
- [ ] Measured storage RPO <= 15 minutes.
- [ ] Measured storage RTO <= 120 minutes.

### 3) Secrets/config recovery validation

- [ ] Runtime secret metadata recovered (secret id + current version stage).
- [ ] App can read required settings after secret recovery.
- [ ] Roll/redeploy confirms new pods resolve required secrets.
- [ ] No startup failures from missing secret keys.
- [ ] Measured secrets RTO <= 45 minutes.

### 4) DNS/ingress validation

- [ ] Ingress controller healthy and serving expected routes.
- [ ] DNS record set points to active load balancer endpoint.
- [ ] TLS certificate chain valid for production domains.
- [ ] External API health check returns successful response.
- [ ] Measured DNS/ingress RTO <= 30 minutes.

## Closeout

- [ ] Actual RPO/RTO documented for each system.
- [ ] Deviations from runbooks listed.
- [ ] Corrective actions created with owner + due date.
- [ ] Final drill report published and linked.
