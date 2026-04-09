# Data classification and handling controls

This document defines MVP production data classes and mandatory controls for customer production onboarding.

## Class definitions

| Class | Description | Typical examples |
| --- | --- | --- |
| **Class A (Restricted / regulated)** | Data that can directly identify a person, reveal authentication material, or materially impact legal/regulatory obligations if disclosed. | Driver phone numbers, auth/session tokens, credential secrets, legal export package contents, audit trails containing user identifiers. |
| **Class B (Sensitive internal)** | Data that is operationally sensitive but lower-impact than Class A when isolated to internal use. | Incident metadata, org configuration, queue/job payload metadata, internal runbook evidence and gate reports. |
| **Class C (Internal baseline)** | Data intended for internal collaboration with minimal confidentiality risk. | Release checklists without customer data, architecture docs, non-secret config defaults, public API schema metadata. |

## Required controls by class

| Control area | Class A (Restricted) | Class B (Sensitive) | Class C (Internal baseline) |
| --- | --- | --- | --- |
| **Access** | Explicit least-privilege RBAC + org tenancy checks; production access requires named user identity and MFA; break-glass access time-boxed and ticketed. | Team-role access with org scoping where applicable; no anonymous access in prod systems. | Standard authenticated employee access; least privilege preferred but broader read access acceptable. |
| **Logging** | Full audit trail for read/write/export/authz decisions; immutable append-only retention target; log redaction for tokens/secrets mandatory. | Security and operational events logged with actor and correlation ids; payload minimization required. | Basic operational logging sufficient; avoid unnecessary personal data in logs. |
| **Retention** | Documented retention schedule with legal hold support; cryptographic delete/backups handling validated; shortest compliant retention defaults. | Time-bound retention with periodic cleanup jobs and owner review each quarter. | Retained for operational convenience; periodic cleanup encouraged. |
| **Audit depth** | Event-level forensic coverage (who/what/when/where/result), export/download traceability, and quarterly control evidence review. | Transaction and configuration-change auditability with monthly spot checks. | Change history or document versioning sufficient for team-level accountability. |

## Baseline enforcement notes

- Class A controls are required before customer production onboarding and are release-gated in production-hardening documentation.
- Any field can be reclassified upward if legal/compliance or customer contract obligations require stricter handling.
- When in doubt, classify data at the higher class and apply stronger controls.
