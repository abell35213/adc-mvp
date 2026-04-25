# Component Migration Map (Page-Specific → Shared)

This map is the source of truth for incremental refactors that move page-specific components into shared directories under `frontend/components` and shared helper modules under `frontend/lib`.

## Destination categories

- `frontend/components/ui`: Primitive UI controls and reusable visual building blocks.
- `frontend/components/layout`: App shell, page frames, section wrappers, and structural composition.
- `frontend/components/data-display`: Tables, cards, badges, timelines, and list/display-only units.
- `frontend/components/case-ops`: Incident/case operations workflows and domain widgets.
- `frontend/components/onboarding`: Onboarding workflow widgets and setup/status surfaces.
- `frontend/components/exports`: Export workflow UI and export status surfaces.
- `frontend/components/integrations`: Integration setup/health widgets and integration status displays.
- `frontend/components/marketing`: Public-site marketing sections and conversion components.
- `frontend/lib/design`: Tokens, theme constants, and design-system configuration.
- `frontend/lib/utils`: Shared utility functions/helpers that are not domain- or API-specific.

## Migration rules for incremental PRs

1. **Move before duplicate**: if a matching pattern already exists in one destination category, move and adapt it instead of creating a duplicate style variant.
2. **Scope by concern**: place components by dominant concern (UI primitive vs. domain workflow vs. marketing).
3. **Extract shared pieces first**: when splitting a page-specific component, first extract reusable pieces into `ui`, `layout`, or `data-display`, then keep route-specific orchestration in the page file.
4. **Tokenize style constants**: replace ad-hoc spacing/color/radius values with shared values in `frontend/lib/design`.
5. **Utility consolidation**: deduplicate formatting/transform helpers into `frontend/lib/utils` when used by 2+ routes/components.

## Current page-specific components and destination map

| Current component/file | Current location | Page/flow affinity | Destination category |
| --- | --- | --- | --- |
| `DashboardClient` | `frontend/app/dashboard/DashboardClient.tsx` | Dashboard route container | `components/layout` (container) + `components/data-display` (extract cards/tables) |
| `IncidentDetailClient` | `frontend/app/incidents/[id]/IncidentDetailClient.tsx` | Incident detail route | `components/case-ops` |
| `OnboardingWizardClient` | `frontend/app/onboarding/OnboardingWizardClient.tsx` | Onboarding landing route | `components/onboarding` |
| `IntegrationSetupPage` | `frontend/app/onboarding/integration-setup/IntegrationSetupPage.tsx` | Onboarding integration setup | `components/onboarding` + `components/integrations` |
| `MappingValidationPage` | `frontend/app/onboarding/mapping-validation/MappingValidationPage.tsx` | Onboarding mapping validation | `components/onboarding` |
| `ProtocolSetupPage` | `frontend/app/onboarding/protocol-setup/ProtocolSetupPage.tsx` | Onboarding protocol setup | `components/onboarding` |
| `QrDeploymentPage` | `frontend/app/onboarding/qr-deployment/QrDeploymentPage.tsx` | Onboarding QR deployment | `components/onboarding` |
| `SampleIncidentValidationPage` | `frontend/app/onboarding/sample-incident-validation/SampleIncidentValidationPage.tsx` | Onboarding sample incident validation | `components/onboarding` + `components/case-ops` |
| `IntegrationConnectionCard` | `frontend/app/settings/integrations/IntegrationConnectionCard.tsx` | Settings integrations | `components/integrations` |
| `IntegrationHealthTable` | `frontend/app/settings/integrations/IntegrationHealthTable.tsx` | Settings integrations | `components/integrations` + `components/data-display` |
| `IntegrationOperationDrawer` | `frontend/app/settings/integrations/IntegrationOperationDrawer.tsx` | Settings integrations | `components/integrations` |
| `IntegrationOperationTable` | `frontend/app/settings/integrations/IntegrationOperationTable.tsx` | Settings integrations | `components/integrations` + `components/data-display` |
| `GenerateExportModal` | `frontend/components/GenerateExportModal.tsx` | Exports flows | `components/exports` |
| `ExportPanel` | `frontend/components/ExportPanel.tsx` | Exports flows | `components/exports` |
| `IncidentDetailExportPanel` | `frontend/components/IncidentDetailExportPanel.tsx` | Incident export in detail route | `components/exports` + `components/case-ops` |
| `MainLayout` | `frontend/components/MainLayout.tsx` | Shared authenticated shell | `components/layout` |
| `AdminLayout` | `frontend/components/AdminLayout.tsx` | Shared admin shell | `components/layout` |
| `Timeline` | `frontend/components/Timeline.tsx` | Timeline route and incident views | `components/data-display` (or `components/case-ops` when incident-only) |
| `EvidenceTable` | `frontend/components/EvidenceTable.tsx` | Evidence-centric views | `components/data-display` + `components/case-ops` |
| `ops.tsx` helpers/components | `frontend/components/ops.tsx` | Ops/admin pages | `components/case-ops` |
| `VehicleImportPreviewTable` | `frontend/components/imports/VehicleImportPreviewTable.tsx` | Import preview flow | `components/data-display` |
| `DriverImportPreviewTable` | `frontend/components/imports/DriverImportPreviewTable.tsx` | Import preview flow | `components/data-display` |
| `CategorizedIssueList` | `frontend/components/imports/CategorizedIssueList.tsx` | Import validation flow | `components/data-display` |
| Marketing section components (`Hero`, `CTASection`, etc.) | `frontend/components/marketing/*` | Public marketing pages | `components/marketing` (already aligned; extract primitives to `components/ui` as needed) |

## Suggested extraction order

1. **Layout foundation**: migrate `MainLayout`/`AdminLayout`, then route shells (`DashboardClient`) to reduce repeated page structure.
2. **Cross-route data display**: migrate shared tables/cards/timeline variants into `data-display`.
3. **Domain workflows**: converge case operations widgets and onboarding panels into their respective domain folders.
4. **Exports + integrations**: finish by consolidating modal/panel/table variants for exports and integration settings.
5. **Design/util pass**: move repeated constants/helpers into `lib/design` and `lib/utils` while preserving route behavior.
