# Playbook: DNS and Ingress Recovery

## Trigger conditions

- DNS records missing or pointed to invalid target.
- Ingress controller outage.
- TLS certificate mismatch/expiration causing service rejection.

## Procedure

1. Verify ingress controller health and service endpoints.
2. Confirm load balancer/NLB endpoint and ingress class are valid.
3. Restore DNS records to known-good target and TTL.
4. Validate TLS certificate and secret references used by ingress.
5. Run external health probe against production hostname.
6. Monitor 4xx/5xx and latency for 30 minutes.

## Validation

- External API health endpoint returns success.
- Authentication and upload paths are reachable externally.
- RTO <= 30 minutes.

## Notes

- Keep IaC-backed DNS records as source of truth.
- Keep a one-command rollback for ingress manifest deploys.
