# Playbook: Object Storage Recovery and Assumptions

## Storage assumptions

- Bucket versioning is enabled for artifacts and exports buckets.
- Lifecycle policy retains non-current versions for at least 90 days.
- Cross-region replication (or scheduled copy) is configured for critical prefixes.
- Object integrity metadata (checksum/hash) exists for sampled evidence objects.

## Trigger conditions

- Accidental delete/overwrite.
- Bucket policy misconfiguration causing object loss/inaccessibility.
- Regional outage impacting primary object storage endpoint.

## Procedure

1. Determine blast radius: single object, prefix, full bucket, or regional scope.
2. For overwrite/delete: restore previous object versions.
3. For widespread corruption: fail over to replicated bucket copy.
4. Rebuild derived artifacts (exports/previews) where needed.
5. Confirm IAM/presigned URL behavior and access control correctness.

## Validation

- Authorized user download for sampled restored objects succeeds.
- Hash/checksum matches object metadata for sampled files.
- Export pipeline includes restored objects without integrity errors.
- RPO <= 15 minutes and RTO <= 120 minutes.
