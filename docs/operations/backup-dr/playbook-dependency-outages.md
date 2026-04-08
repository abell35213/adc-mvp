# Playbook: Key Dependency Outages

## Dependencies covered

- Secrets manager.
- Object storage provider.
- DNS provider.
- OTP/SMS provider.
- Payment/identity or other customer-facing upstreams (as applicable).

## Triage matrix

| Dependency | Degradation symptom | Immediate mitigation |
| --- | --- | --- |
| Secrets manager | Pod restart loops / missing secrets | Pin to cached version; recover secret version stage; reduce restarts |
| Object storage | Upload/download failures | Queue writes, switch to replicated region, disable non-essential exports |
| DNS provider | Domain unreachable | Fail over via secondary DNS or static fallback records |
| OTP provider | Login/verification failures | Use backup channel/provider; temporary grace for active sessions |

## Generic response procedure

1. Declare incident and assign IC.
2. Confirm upstream status and scope of impact.
3. Enable feature flags/degraded mode to protect core write paths.
4. Fail over to redundant provider/region where available.
5. Communicate customer impact and workaround expectations.
6. Track elapsed time against dependent service RTO.

## Recovery validation

- Error rates return to baseline for dependency-specific endpoints.
- Queued/retried jobs drain without manual replay gaps.
- Follow-up action items include stronger fallback/abstraction coverage.
