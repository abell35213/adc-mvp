# ADC Exports & Documents

## Page purpose
Exports & Documents is the organization-scoped operational surface for generated defense documents. It helps users identify existing documents, their cases, their readiness, who requested them when available, and the next safe action.

## Information hierarchy
The hierarchy is page header, supported operational metrics, compact filters, document list/table, mobile document cards, and a detail drawer for status, requirements, file details, generation history, contents, and collapsed technical details.

## Document-title strategy
Document names are derived in the export document view model from supported export types: Legal Defense Packet, Insurance Notice, Crash Executive Brief, and Agency Packet. API-provided `document_title` in `options_json` can override this when authoritative. Raw export IDs are never primary labels.

## Status definitions
Supported statuses remain the backend contract: `requested`, `queued`, `processing`, `ready`, `failed`, and `expired`. Requested/queued/processing are active states, ready is downloadable, failed needs attention, and expired means download access is no longer available.

## Progress/stage rules
The backend provides discrete `progress_stage` values rather than authoritative percentages. The UI therefore displays readable stages such as Preparing case data, Rendering packet, Packaging evidence, Uploading document, and Ready for download; it does not synthesize progress percentages.

## Action hierarchy
Rows/cards show one primary contextual action: Download for ready documents, Review issue for failed documents, Regenerate/View status for expired or active documents. Secondary actions live in the dropdown: view details, view case, retry, copy export ID, and copy case ID.

## Failure-message policy
Failure messaging is sanitized through the export document view model. Known failure codes become actionable copy. Unknown or technical-looking values are replaced with a generic safe rendering-failed message and users keep the export ID in technical details for support.

## Retry versus regenerate semantics
Retry is exposed only for failed exports and calls the existing retry endpoint to reuse the failed generation configuration. Regenerate is presented as an expired/ready semantic where supported by existing workflows; no unsupported backend endpoint was added.

## Download behavior
Ready documents use Download as the primary action and call the existing download endpoint. Presigned URLs are opened via the existing safe URL helper and are not displayed as text.

## Expiration behavior
Expired documents explain that the download is no longer available. The current backend returns `expired` as a terminal status; users are directed to regenerate from case context where supported.

## Technical-detail disclosure
Full export IDs, incident IDs, raw status/stage, and package checksums live inside a collapsed Technical details disclosure in the drawer or copy actions in row menus.

## Incident integration
The incident Documents tab uses the shared export document list, shared status/stage mapping, the existing generation modal, existing polling, existing retry endpoint, and existing download endpoint. It filters naturally to the incident exports passed by the incident detail API.

## Global list behavior
The global page lists exports returned by `/exports/`, filters loaded records by search/status, and sorts loaded records by operational priority, newest, oldest, case, or document type. Search is limited to loaded record fields.

## Responsive behavior
Desktop uses a structured table. Mobile uses document cards with title, case, status, stage, generated timestamp, requested-by label, primary action, and secondary menu. No full-width horizontal workflow scroll is required for mobile use.

## Accessibility behavior
The page has one h1, labeled filter controls, a table caption, explicit document action names, readable status labels, absolute timestamp values on time elements, keyboard-operable primitive dropdown/drawer controls, and technical details behind disclosure.

## Backend contract changes
No backend contract changes were made in this phase. The frontend safely consumes current fields and optional metadata from `options_json` when already present.

## Demo-seed changes
No demo seed changes were made.

## Legacy components migrated
The global exports page migrated from bespoke cards and drawer markup to shared Button, StatusBadge, Card, MetricCard, Drawer, FormField, Input, Select, Alert, EmptyState, Skeleton, Avatar, DropdownMenu, and table foundation primitives. IncidentDetailExportPanel now uses the shared document list and shared alerts for workflow feedback.

## Remaining Phase 6 dependencies
Authoritative backend fields remain desirable: case reference, incident display context, requested-by display name, safe failure reason/failure code, file name, file type, file size, version, preview availability, and explicit regenerate support.
