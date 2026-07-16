# ADC Design System Foundations

## Principles
ADC UI should feel calm under pressure, trustworthy, decisive, operational, modern, professional, and visually restrained. Use neutral canvas backgrounds, white surfaces, subtle borders, minimal elevation, one primary blue, restrained semantic status colors, consistent type and spacing, and visible focus states.

## Token categories
Tokens are consolidated in `frontend/app/globals.css` for Tailwind v4 CSS variables and `frontend/lib/design/tokens.ts` for TypeScript class maps. Categories include background, text, border, action, status, spacing, typography, radius, elevation, control dimensions, icon sizes, and restrained transitions.

## Component inventory
Reusable primitives live in `frontend/components/ui`: Button, IconButton, Badge, StatusBadge, Card, MetricCard, PageHeader, Breadcrumbs, Tabs, SegmentedControl, ProgressBar, Avatar, EmptyState, Skeleton, Alert, Tooltip, DropdownMenu, Modal, Drawer, FormField, Input, Select, Textarea, and table foundation helpers.

## Usage guidance
Compose domain screens from `components/ui` primitives. Keep page-specific layout glue local, but avoid recreating button, badge, card, form, dialog, drawer, and table visuals with long Tailwind strings.

## Button hierarchy
Use `primary` for the single most important action, `secondary` for supportive actions, `quiet` for low-emphasis utility actions, and `destructive` only for irreversible or harmful actions. Loading buttons must provide a readable loading label.

## Status usage
Use neutral, informational, success, warning, and critical. Status UI must include readable text; dot or icon accents are optional and cannot be the only signal.

## Spacing guidance
Use an 8-pixel-oriented scale: 4, 8, 12, 16, 20, 24, 32, 40, 48, and 64. Prefer predictable card padding and gaps over one-off values.

## Typography guidance
Use page title, section title, card title, body, body small, metadata, label, metric, and code styles from the token map. Avoid widespread uppercase labels.

## Accessibility expectations
All interactive primitives must expose visible focus states, accessible names where required, correct disabled behavior, ARIA semantics for tabs/progress/dialogs, Escape handling for modal/drawer, return focus, and status text that does not rely on color alone.

## Deprecated components
Legacy visual seeds remain for compatibility: `data-display/StatusChip`, `MetricCard`, `EmptyStateCard`, `SkeletonTable`, `ErrorStateBanner`, `layout/PageHeader`, and `layout/SectionCard`. They should be migrated toward `components/ui` in later phases rather than duplicated.

## Migration guidance
Phase 2 should extract app shell components into `frontend/components/app-shell`. Later phases should replace inline operational controls with `Button`, `StatusBadge`, `Card`, `PageHeader`, `DataTable` helpers, and form primitives while preserving routes and workflows.

## Legacy cleanup backlog
Raw Tailwind color/status/button/card class strings remain across login, shell, dashboard, incident detail, exports, reports, and admin surfaces by design. Those screens are intentionally not comprehensively redesigned in Phase 1.

## Phase 2 shell and navigation guidance
Authenticated product screens should use `frontend/components/app-shell/AppShell` through the existing `MainLayout` and `AdminLayout` compatibility wrappers. The shell owns the desktop sidebar, mobile drawer navigation, top bar, user menu, skip link, page canvas, and authenticated `PageContainer` spacing. Do not recreate separate sidebar/header systems for admin or incident pages; use the shell variant when an admin navigation emphasis is required.

Primary navigation labels are Command Center, Cases, Evidence, Exports, Vehicles, and Reports. Secondary navigation labels are Settings, Help, and Administration. Navigation visibility must continue to be driven by `hasRoleCapability`, and active states must combine text, background, and the left indicator rather than color alone.

Global top-bar actions should stay restrained. `Create Incident` is the persistent primary action. Page-specific operational actions belong in each page header or content section.

Login screens should use `Card`, `FormField`, `Input`, `Button`, and `Alert`, keep demo credentials gated by non-production demo environment configuration, and avoid exposing raw provider or API internals in user-facing errors.

## Phase 3 Command Center guidance
The authenticated dashboard composes the existing Phase 1 primitives rather than defining a dashboard-only visual language. Use `PageHeader` for the page title/action hierarchy, four `MetricCard` components for operational metrics, `Card`/`TableContainer` for the Priority Case Queue, `StatusBadge` for case status, `ProgressBar` for readiness, `Avatar` for owner affordances, `DropdownMenu` for secondary row actions, `FormField` with `Input`/`Select` for filters, `EmptyState` for no-data states, `Skeleton` for loading states, and `Alert` for partial and full failure states.

Dashboard status color should be restrained: status belongs in badges, progress indicators, and alerts, not as full-row tints or large colored panels. The queue should remain visually dominant; Needs Attention is a secondary panel summarizing actionable categories without duplicating the full table.

## Phase 4 Incident Workspace guidance
Incident workspace screens should compose the Phase 1 primitives and Phase 2 application shell rather than introducing an incident-specific design system. Use a structured case header for the primary case reference, title/type, status, date/time, location, owner, last update, readiness, and one primary next action. Keep raw UUIDs available through copy actions or collapsed technical details, not as primary headings. Use restrained tabs for Overview, Evidence, Timeline, Documents, and Activity; preserve query-state deep links where practical. Desktop action rails may be sticky only when narrow, non-overlapping, and keyboard order remains logical; on mobile they should stack inline. Timeline raw payloads and technical metadata belong behind keyboard-accessible disclosures.

## Phase 5 export/document guidance
Export and document screens should use the shared export document view model for title, status, stage, action, file metadata, safe failure messages, and technical-ID fallback. Use `StatusBadge` for document state, `MetricCard` only for data-backed operational counts, table foundations on desktop, document cards on mobile, and `Drawer`/`Alert`/`EmptyState`/`Skeleton` for detail and workflow feedback. Do not create export-specific button, badge, modal, or table styles.
