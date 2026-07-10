# P0 Migration Baseline Audit

Generated during the 2026-07-10 pre-production migration repair. The active Alembic history is now a reviewed MVP baseline; the broken historical chain is archived under `backend/app/db/migrations/archived_broken_history_20260710/`.

## Table lineage from archived history

| Table | ORM model | Archived creation revision | First archived reference | Later archived references |
|---|---|---:|---:|---|
| `artifacts` | `Artifact` | 0001 | 0001 | 0003, 0004, 0008, 0030, 0034 |
| `audit_events` | `AuditEvent` | 0015 | 0015 | 0030 |
| `case_notes` | `CaseNote` | 0018 | 0018 | 0030 |
| `case_readiness_overrides` | `CaseReadinessOverride` | 0018 | 0018 | 0030 |
| `case_tasks` | `CaseTask` | 0018 | 0018 | 0030 |
| `crash_packet_deliveries` | `CrashPacketDelivery` | 0031 | 0031 | — |
| `demo_scenarios` | `DemoScenario` | 0025 | 0025 | 0030 |
| `deployment_scope_snapshots` | `DeploymentScopeSnapshot` | 0025 | 0025 | 0030 |
| `dispatch_instructions` | `DispatchInstruction` | 0034 | 0034 | — |
| `driver_import_jobs` | `DriverImportJob` | 0026 | 0026 | 0030 |
| `driver_instruction_sets` | `DriverInstructionSet` | 0005 | 0005 | 0030 |
| `driver_instruction_steps` | `DriverInstructionStep` | 0005 | 0005 | 0030 |
| `driver_unit_history` | `DriverUnitHistory` | 0035 | 0035 | — |
| `driver_vehicle_assignments` | `DriverVehicleAssignment` | 0005 | 0005 | 0030 |
| `drivers` | `Driver` | 0005 | 0005 | 0030 |
| `events` | `Event` | 0001 | 0001 | 0003, 0004, 0014, 0030 |
| `evidence_requests` | `EvidenceRequest` | MISSING | 0030 | — |
| `expansion_readiness_snapshots` | `ExpansionReadinessSnapshot` | 0025 | 0025 | 0030 |
| `exports` | `Export` | 0001 | 0001 | 0003, 0004, 0009, 0010, 0011, 0029, 0030 |
| `external_mappings` | `ExternalMapping` | MISSING | 0030 | — |
| `fmcsa_inspection_snapshots` | `FmcsaInspectionSnapshot` | 0035 | 0035 | — |
| `fmcsa_inspections` | `FmcsaInspection` | 0035 | 0035 | — |
| `help_article_views` | `HelpArticleView` | 0025 | 0025 | 0030 |
| `help_articles` | `HelpArticle` | 0025 | 0025 | 0030 |
| `help_categories` | `HelpCategory` | 0025 | 0025 | 0030 |
| `incident_driver_violation_history` | `IncidentDriverViolationHistory` | 0035 | 0035 | — |
| `incidents` | `Incident` | 0001 | 0001 | 0002, 0003, 0004, 0018, 0023, 0030, 0032 |
| `insurance_form_fillings` | `InsuranceFormFilling` | 0033 | 0033 | — |
| `insurance_form_template_fields` | `InsuranceFormTemplateField` | 0033 | 0033 | — |
| `insurance_form_templates` | `InsuranceFormTemplate` | 0033 | 0033 | — |
| `integration_connections` | `IntegrationConnection` | MISSING | 0030 | — |
| `integration_operation_status_history` | `IntegrationOperationStatusHistory` | MISSING | 0030 | — |
| `integration_operations` | `IntegrationOperation` | MISSING | 0030 | — |
| `integration_validation_results` | `IntegrationValidationResult` | 0022 | 0022 | 0030 |
| `job_execution_meta` | `JobExecutionMeta` | 0016 | 0016 | — |
| `loading_dock_reports` | `LoadingDockReport` | 0034 | 0034 | — |
| `maintenance_records` | `MaintenanceRecord` | 0032 | 0032 | — |
| `message_operation_status_history` | `MessageOperationStatusHistory` | 0017 | 0017 | 0030 |
| `message_operations` | `MessageOperation` | MISSING | 0017 | 0030 |
| `org_export_validation_runs` | `OrgExportValidationRun` | 0024 | 0024 | 0030 |
| `org_launch_readiness_blockers` | `OrgLaunchReadinessBlocker` | 0019 | 0019 | 0030 |
| `org_launch_readiness_snapshots` | `OrgLaunchReadinessSnapshot` | 0019 | 0019 | 0030 |
| `org_launch_readiness_step_progress` | `OrgLaunchReadinessStepProgress` | 0019 | 0019 | 0030 |
| `org_notification_recipients` | `OrgNotificationRecipient` | 0031 | 0031 | — |
| `org_onboarding_step_completions` | `OrgOnboardingStepCompletion` | 0020 | 0020 | 0030 |
| `org_plan_entitlements` | `OrgPlanEntitlement` | 0025 | 0025 | 0030 |
| `org_test_incident_runs` | `OrgTestIncidentRun` | 0023 | 0023 | 0030 |
| `org_user_invites` | `OrgUserInvite` | 0028 | 0028 | 0030 |
| `org_vehicle_registry` | `OrgVehicleRegistry` | MISSING | 0021 | 0030, 0035 |
| `orgs` | `Org` | 0002 | 0002 | 0005, 0006, 0014, 0020, 0030, 0035 |
| `otp_challenges` | `OtpChallenge` | 0005 | 0005 | 0007 |
| `provider_webhook_events` | `ProviderWebhookEvent` | MISSING | 0027 | 0030 |
| `refresh_tokens` | `RefreshToken` | 0012 | 0012 | 0030 |
| `sessions` | `SessionRecord` | 0012 | 0012 | 0029, 0030 |
| `tms_connections` | `TmsConnection` | 0032 | 0032 | — |
| `tms_field_maps` | `TmsFieldMap` | 0032 | 0032 | — |
| `trailers` | `Trailer` | 0032 | 0032 | — |
| `trust_sections` | `TrustSection` | 0025 | 0025 | 0030 |
| `user_orgs` | `UserOrg` | 0002 | 0002 | 0030 |
| `users` | `User` | 0002 | 0002 | 0014, 0018, 0030 |
| `vehicle_import_jobs` | `VehicleImportJob` | MISSING | 0030 | — |
| `vehicle_qr_tokens` | `VehicleQrToken` | 0005 | 0005 | 0030 |
| `weigh_station_reports` | `WeighStationReport` | 0034 | 0034 | — |

## Missing historical table creation defects

The archived chain referenced or needed these ORM tables but never created them with `op.create_table()`:
- `integration_connections`: ORM-defined, archived creation revision MISSING, first archived reference 0030.
- `integration_operations`: ORM-defined, archived creation revision MISSING, first archived reference 0030.
- `integration_operation_status_history`: ORM-defined, archived creation revision MISSING, first archived reference 0030.
- `evidence_requests`: ORM-defined, archived creation revision MISSING, first archived reference 0030.
- `external_mappings`: ORM-defined, archived creation revision MISSING, first archived reference 0030.
- `provider_webhook_events`: ORM-defined, archived creation revision MISSING, first archived reference 0027.
- `message_operations`: ORM-defined, archived creation revision MISSING, first archived reference 0017.
- `org_vehicle_registry`: ORM-defined, archived creation revision MISSING, first archived reference 0021.
- `vehicle_import_jobs`: ORM-defined, archived creation revision MISSING, first archived reference 0030.

## Baseline repair decision

Because the archived pre-production migration chain was materially incomplete (54 created ORM tables versus 63 ORM tables, plus named PostgreSQL enum lifecycle defects), the repair uses a single active baseline revision for the intended MVP schema. Archived revisions are retained only as reference and are not loaded by Alembic.
