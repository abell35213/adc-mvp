# ADC Frontend Visual Audit and Redesign Plan

## 1. Executive summary

The ADC frontend already has the beginning of an application design system: Tailwind v4 theme variables in `frontend/app/globals.css`, semantic-ish utility bundles in `frontend/lib/design/tokens.ts`, and reusable layout/data-display components under `frontend/components/layout` and `frontend/components/data-display`. However, the product UI is still split between at least three visual languages:

1. **Newer operations shell language** using `bg-page`, `bg-surface`, `text-text-*`, `border-border-*`, and status tokens.
2. **Legacy Tailwind default language** using raw `gray`, `blue`, `green`, `red`, `yellow`, `amber`, fixed shadows, and unscoped radii.
3. **Marketing language** using separate hardcoded brand hex values and rounded consumer-style cards.

For the Phase 1 redesign, the safest path is not to introduce a large component library. The current stack is small (`next`, `react`, `tailwindcss`, TypeScript, and no UI component dependency), so ADC should evolve the existing primitives into a focused internal design system. The target should be a calm, high-trust B2B SaaS interface with a neutral gray canvas, white surfaces, restrained status treatments, one primary blue, strong content hierarchy, and fewer simultaneous actions.

Demo-critical surfaces should be sequenced as: login, application shell, command-center dashboard, incident detail, then exports/documents. The primary architectural risk is duplicate implementations: layout wrappers, export panels/modals, evidence tables, timeline components, support/report/case-ops panels, and one-off page headers/cards/buttons all exist in parallel.

## 2. Files inspected

### Required areas inspected

- `frontend/app`
- `frontend/components`
- `frontend/lib/design`
- `frontend/app/globals.css`
- Tailwind configuration discovery: no standalone `tailwind.config.*` file was found under `frontend`; Tailwind v4 theme configuration is inline in `frontend/app/globals.css`.
- `frontend/package.json`
- Layout components:
  - `frontend/components/layout/MainLayout.tsx`
  - `frontend/components/MainLayout.tsx`
  - `frontend/components/layout/AdminLayout.tsx`
  - `frontend/components/AdminLayout.tsx`
  - `frontend/components/layout/PageHeader.tsx`
  - `frontend/components/layout/SectionCard.tsx`
  - `frontend/components/layout/StickySidebar.tsx`
  - `frontend/components/layout/RightRailPanel.tsx`
- Sidebar/navigation components:
  - `frontend/components/layout/MainLayout.tsx`
- Page-header components:
  - `frontend/components/layout/PageHeader.tsx`
  - local headers in dashboard, exports, incident detail, login, resources pages
- Button, card, badge, status, table, form, modal/drawer patterns across:
  - `frontend/components/case-ops/*`
  - `frontend/components/data-display/*`
  - `frontend/components/exports/*`
  - `frontend/components/integrations/*`
  - `frontend/components/imports/*`
  - `frontend/components/onboarding/*`
  - `frontend/components/reports/*`
  - top-level compatibility re-exports in `frontend/components/*`
- Demo-critical pages:
  - `frontend/app/login/page.tsx`
  - `frontend/app/dashboard/page.tsx`
  - `frontend/app/dashboard/DashboardClient.tsx`
  - `frontend/app/incidents/[id]/page.tsx`
  - `frontend/app/incidents/[id]/IncidentDetailClient.tsx`
  - `frontend/app/exports/page.tsx`
  - `frontend/app/resources/docs/page.tsx`
  - `frontend/app/resources/sample-documents/page.tsx`

## 3. Current-state findings

### 3.1 Existing design tokens and usage

Current tokens are split between CSS custom properties and TypeScript class bundles.

#### CSS theme tokens

`frontend/app/globals.css` defines:

- Shell/page/surface colors: `--shell`, `--page`, `--surface`, `--surface-muted`, `--surface-elevated`.
- Borders: `--border-default`, `--border-subtle`, `--border-strong`.
- Text: `--text-primary`, `--text-secondary`, `--text-muted`, `--text-inverse`.
- Accent: `--accent`, `--accent-strong`, `--accent-soft`.
- Status: success, warning, critical, info and soft variants.
- Radius: sm through xl.
- Shadows: card, card hover, panel.
- Tailwind v4 `@theme inline` aliases for the above.

These tokens are used heavily in `MainLayout`, `PageHeader`, `SectionCard`, `IncidentQueueTable`, `ExportsPage`, and data-display primitives.

#### TypeScript class tokens

`frontend/lib/design/tokens.ts` exports:

- `StatusTone` and `statusBadgeClass()`.
- `designTokens.shell`, `page`, `surface`, `border`, `text`, `accent`, `radius`, `shadow`, `status`, and `control`.

Current usage is inconsistent. Some components use `designTokens.control.input` and `statusBadgeClass`; many others still hardcode raw Tailwind colors and control classes.

### 3.2 Hardcoded values

Hardcoded values are widespread across operational UI:

- Colors: `bg-gray-50`, `bg-white`, `text-gray-900`, `text-blue-600`, `bg-blue-600`, `bg-green-100`, `bg-red-50`, `text-yellow-800`, `bg-[#0b1633]`.
- Spacing: repeated `p-4`, `p-5`, `p-6`, `px-3 py-2`, `gap-4`, `space-y-4`, `space-y-6`.
- Radii: repeated `rounded`, `rounded-md`, `rounded-lg`, `rounded-xl`, and marketing-only `rounded-2xl`/`rounded-3xl`.
- Shadows: `shadow`, `shadow-sm`, `shadow-card`, `shadow-xl`, `shadow-panel` mixed without hierarchy.
- Font sizes: many one-off `text-[11px]`, `text-xs`, `text-sm`, `text-2xl`, `tracking-[0.12em]`, `tracking-[0.14em]` values.
- Widths: fixed shell/sidebar values such as `w-72`, `max-w-7xl`, `max-w-6xl`, `max-w-5xl`, `min-w-[980px]`, and drawer `max-w-2xl`.

### 3.3 Navigation and layout state

The application shell is serviceable but visually heavy. The sidebar uses a dark hardcoded navy and multiple quick actions in the top header. Header breadcrumbs truncate IDs rather than replacing them with human-readable case labels. Mobile behavior is incomplete because the sidebar is hidden at `lg` and no equivalent mobile navigation is present.

### 3.4 Raw identifiers and human readability

Raw or shortened technical IDs appear in demo-critical flows:

- Incident detail hero shows `Case {incidentId.slice(0, 8)}…`.
- Incident queue shows shortened incident IDs and owner user IDs in monospace.
- Exports page filters by export ID, incident ID, or SHA and displays short export IDs.
- Export detail drawer displays full export ID, incident ID, SHA256, and raw JSON options as primary metadata.
- Breadcrumbs detect UUID-like segments and truncate them rather than resolving case names.

Recommended primary labels:

- Case title: `Case #ADC-YYYY-NNNN` or `Incident opened Jul 15, 2:28 PM`.
- Vehicle: human-readable unit/plate/VIN last 6 before internal IDs.
- Driver: name or driver number before `adc_driver_id`.
- Export: packet type + created date + status before export ID.
- SHA/UUIDs: secondary metadata in copyable rows.

## 4. Screen inventory

| Route | Purpose | Primary user | Primary user action | Current visual problems | Components used | Redesign priority |
|---|---|---:|---|---|---|---:|
| `/login` | Authenticate app users and optionally demo sandbox users | All users, demo evaluator | Sign in | Separate dark-mode/default Tailwind visual language; no app shell brand alignment; small generic form; hardcoded colors; missing visible focus styling beyond browser default | Local form only | P0 |
| App shell around `/dashboard`, `/incidents`, `/exports`, `/vehicles`, admin pages | Persistent navigation, tenant context, quick actions | Operators, safety managers, admins, legal reviewers | Navigate and trigger common actions | Hardcoded dark sidebar; no mobile nav; too many global quick actions; role/org IDs visible; mixed top header and page headers; breadcrumb ID truncation | `MainLayout`, local nav arrays, inline breadcrumbs/actions | P0 |
| `/dashboard` | Command Center queue and operational overview | Operator, safety manager | Triage highest-priority case, assign/restatus incident | Dense mixed panels; too many status colors/actions; local tabs/buttons; filters and tabs compete with queue; onboarding panels may crowd incident response | `MainLayout`, `PageHeader`, `SectionCard`, `IncidentSummaryCards`, `IncidentQueueTable`, alert/task panels | P0 |
| `/incidents` | Incident list/queue | Operator, safety manager | Find/open incidents | Similar to dashboard queue but likely less prominent than command center; table min width creates mobile overflow | `MainLayout`, case-ops filters/table | P1 |
| `/incidents/[id]` | Work an incident case through evidence, tasks, notes, readiness, export | Operator, legal reviewer | Resolve next action and generate packet | Does not use app shell; raw/short ID hero; many competing bordered cards; numerous raw gray/blue/green/red classes; sticky right rail can overwhelm; status conveyed with color chips; loading/error states detached from shell | `CaseHeroHeader`, `EvidenceStatusPanel`, `TimelineFeed`, `CaseTasksPanel`, `CaseNotesPanel`, `StickySidebar`, export panel | P0 |
| `/exports` | Track generated/requested evidence packets and inspect/download details | Legal reviewer, operator | Download, retry, inspect export packet | Duplicate header; list + drawer built ad hoc; raw IDs/SHA as primary; drawer lacks accessible dialog semantics; actions compete in each list item | `MainLayout`, `ExportListItem`, inline drawer, `designTokens.control.input` | P0 |
| `/resources/docs` | Marketing/resource documentation page | Evaluator, admin | Read documentation/contact support | Marketing page rather than authenticated document center; not part of app shell; lightweight placeholder cards; consumer marketing styling | Marketing CTA components/local cards | P1 for app docs, P2 for marketing |
| `/resources/sample-documents` | Show sample export PDFs | Evaluator | Preview/download sample docs | Marketing carousel patterns should not leak into authenticated document center | `SampleDocumentsCarousel` | P1 |
| `/timeline` | Timeline overview | Operator | Review events | Needs consistency check after shell redesign | `MainLayout`, timeline/data display components | P2 |
| `/vehicles`, `/admin/vehicles` | Vehicle QR and admin vehicle management | Admin, safety manager | Manage vehicles/QRs | Forms/tables likely duplicate import/admin controls; should inherit shared table/form patterns | `MainLayout`/admin components | P2 |
| `/reports` | Operational reports | Manager | Review metrics/follow-ups | Duplicate report panels with case-ops/support equivalents | report components | P2 |
| `/settings/integrations` | Integration operation status | Admin | Inspect/retry integration operations | Integration tables use raw grays and legacy statuses | integration components | P2 |

## 5. Component inventory

| Primitive | Current implementations | Assessment | Proposed reusable primitive | Action |
|---|---|---|---|---|
| Button | Inline buttons across login, queue, incident panels, exports modal/list, marketing CTAs | Many repeated sizes/colors; disabled/focus inconsistent | `Button` with `variant=primary/secondary/tertiary/danger/success`, `size=sm/md/lg`, loading state | Consolidate/refactor |
| IconButton | Minimal explicit app primitive; icon-only buttons mainly marketing/carousel-like | Risk of unlabeled controls as icons are added | `IconButton` requiring `aria-label` | Add |
| Badge | `StatusChip`, `statusBadgeClass`, inline rounded spans | Duplicated tones and sizes | `Badge` + `StatusBadge` | Consolidate |
| StatusBadge | `StatusChip`, `EvidenceStatusBadge`, inline status maps, readiness/case meta | Status taxonomies split | `StatusBadge` backed by `lib/status` metadata and semantic tones | Refactor |
| Card | `SectionCard`, local `rounded-lg border bg-white p-* shadow-sm`, data-display cards | Visual hierarchy inconsistent | `Card` with `tone`, `padding`, optional header/footer | Consolidate |
| MetricCard | `MetricCard`, `IncidentSummaryCards`, reports summary cards, exports count cards | Similar metric layouts duplicated | `MetricCard` with label/value/trend/tone | Consolidate |
| PageHeader | `layout/PageHeader` plus local page headers and shell title | Duplicate title/action areas | `PageHeader` with eyebrow, title, description, meta, primary/secondary actions | Retain/refactor |
| Breadcrumbs | Inline in `MainLayout` | Not reusable and ID handling weak | `Breadcrumbs` with resolved labels | Extract |
| Tabs | Inline queue tabs, sample-doc tabs | No app tab primitive | `Tabs` or `SegmentedControl` for status queues | Add |
| SegmentedControl | Inline button groups in queue/filter areas | Repeated selected/unselected classes | `SegmentedControl` | Add |
| DataTable | `DataTableShell`, `EvidenceTable`, queue table, integration/import tables | Multiple tables with accessibility/responsive inconsistencies | `DataTable` + `TableToolbar` + `ResponsiveTableContainer` | Consolidate |
| DropdownMenu | Native `select` controls only | OK for now; no heavy dependency needed | Native select styled through `SelectField`; consider menu only if needed | Defer/add later |
| Avatar | `AvatarChip` | Keep but align tokens | `Avatar`/`AvatarChip` | Retain/refactor |
| ProgressBar | `ReadinessProgressBar`, custom completeness percentages | Duplicated readiness/progress displays | `ProgressBar` with label/value/tone | Consolidate |
| EmptyState | `EmptyStateCard`, inline “No exports/incidents” text | Empty states inconsistent | `EmptyState` with title/body/action | Consolidate |
| Skeleton | `SkeletonTable`, local loading text | Loading states inconsistent | `Skeleton`, `SkeletonTable`, `PageSkeleton` | Retain/refactor |
| Alert | `ErrorStateBanner`, inline red/blue/green panels | Alerts are one-off | `Alert` with `tone`, title/body/action | Consolidate |
| Toast | Not observed as shared primitive | Success/error feedback mostly inline | Add minimal toast only if product needs transient confirmation | Add later |
| Modal | `GenerateExportModal`, inline overlays | Dialog semantics and focus management missing | `Modal` with focus trap/escape/labeling | Add/refactor |
| Drawer | Export detail inline fixed aside | No shared primitive or ARIA dialog role | `Drawer` with title/description/actions | Add |
| Tooltip | Not observed | Avoid unless needed; high-stakes UI should not hide required info | Defer |
| Form fields | Inline `input`, `select`, checkbox labels | Inconsistent labels, help/error, focus | `TextField`, `SelectField`, `CheckboxField`, `FieldError` | Add |

### Existing components to retain

- `frontend/components/layout/MainLayout.tsx` as the shell foundation, but refactor into smaller shell/nav/breadcrumb components.
- `frontend/components/layout/PageHeader.tsx` with stronger variants and action hierarchy.
- `frontend/components/layout/SectionCard.tsx` as the basis for `Card`.
- `frontend/components/data-display/StatusChip.tsx`, `MetricCard.tsx`, `EmptyStateCard.tsx`, `SkeletonTable.tsx`, and `ErrorStateBanner.tsx` as seeds for primitives.
- `frontend/lib/status` as the central status metadata layer.

### Existing components to refactor

- `CaseHeroHeader`, `IncidentQueueTable`, `CaseOwnerControl`, `CaseTasksPanel`, `CaseNotesPanel`, `CaseReadinessCard`, `TimelineFeed`, and `EvidenceStatusPanel` should consume shared primitives.
- `ExportListItem`, `IncidentDetailExportPanel`, and `GenerateExportModal` should consume `Button`, `StatusBadge`, `Card`, `Modal`, and `Drawer`.
- `LoginPage` should use app tokens and form/button primitives.

### Existing components to consolidate or remove

- Top-level re-export shims (`frontend/components/MainLayout.tsx`, `AdminLayout.tsx`, `GenerateExportModal.tsx`, `ExportPanel.tsx`, `IncidentDetailExportPanel.tsx`, `EvidenceTable.tsx`) should be retained temporarily for compatibility but removed after imports converge.
- Duplicate panels between `case-ops`, `support`, and `reports` should be merged where props match.
- Duplicate `Timeline` implementations should be merged into one timeline primitive plus case-specific adapters.
- Duplicate `EvidenceStatusPanel` components under `case-ops` and `integrations` should share status/table primitives, even if domain-specific wrappers remain.

## 6. Duplicate implementation findings

1. **Layout wrappers:** `frontend/components/MainLayout.tsx` re-exports `layout/MainLayout`; `AdminLayout` has a similar compatibility layer. This is acceptable short-term but should be cleaned once imports are normalized.
2. **Export modals/panels:** `frontend/components/GenerateExportModal.tsx` re-exports `frontend/components/exports/GenerateExportModal.tsx`; export panels also exist both top-level and in `exports`.
3. **Evidence tables:** top-level `EvidenceTable` and `data-display/EvidenceTable` create likely table styling drift.
4. **Timeline:** top-level `Timeline`, `data-display/Timeline`, and `case-ops/TimelineFeed` overlap.
5. **Summary cards:** `case-ops/IncidentSummaryCards` and `reports/IncidentSummaryCards` overlap.
6. **Support/case panels:** `MissingItemsPanel`, `CaseNotesPanel`, `CaseTasksPanel`, and `AlertsPanel` exist in both `case-ops` and `support` or reports-adjacent folders.
7. **Status badges:** `StatusChip`, `EvidenceStatusBadge`, and inline rounded spans duplicate tone mapping.
8. **Cards/page sections:** `SectionCard` exists, but many pages use local `rounded-lg border bg-white p-* shadow-sm` instead.
9. **Buttons:** primary/secondary/danger/success buttons are recreated inline in every demo-critical surface.
10. **Drawer/modal overlays:** export detail drawer and generate export modal are bespoke overlays with similar fixed positioning, backdrops, close buttons, and shadows.

## 7. Accessibility findings

### 7.1 Contrast and color

- Some muted text (`text-gray-400`, `text-slate-300/90`, `text-text-muted`) may be too subtle on colored/dark surfaces and should be checked with automated contrast tooling after token finalization.
- Status colors frequently use very light backgrounds and colored text. This can work, but tones should be standardized and checked for WCAG AA for normal text.
- Status meaning is sometimes conveyed by color plus label, which is acceptable; ensure all future status icons/chips keep text labels.

### 7.2 Focus states

- Many app buttons/links rely on default browser focus or only `hover` states.
- Marketing tokens include `focus-visible` rings more consistently than authenticated app controls.
- Shared `Button`, `IconButton`, form fields, tabs, modal close controls, and nav links should include a consistent `focus-visible:ring-2 focus-visible:ring-action-primary focus-visible:ring-offset-2` style.

### 7.3 Icon-only and low-label controls

- Current app controls are mostly text buttons. Future icon buttons must require `aria-label` through prop typing.
- Carousel/marketing controls already include labels in several places; app primitives should enforce the same standard.

### 7.4 Heading hierarchy

- The app shell renders an `h1` in the top header, while pages and page cards often render additional `h1`/`h2` headings. Dashboard and exports can have duplicate or unclear top-level headings.
- Incident detail does not use `MainLayout`, so hierarchy differs from the rest of the app.
- Recommendation: shell should render contextual chrome but page content owns the single `h1` through `PageHeader`.

### 7.5 Tables

- Queue and integration/evidence tables lack explicit captions or `aria-label`s.
- Table headers exist, but controls embedded inside dense rows can be difficult to navigate.
- Add `caption` or `aria-label`, consistent `scope="col"`, row action grouping, and responsive fallbacks.

### 7.6 Modals/drawers

- Export detail drawer is a fixed `aside` without `role="dialog"`, `aria-modal`, focus trap, Escape close handling, or labelled title wiring.
- Generate export modal similarly needs shared modal semantics and focus management.

### 7.7 Forms

- Login labels are visible and inputs are required, but there is no `aria-describedby` for errors.
- Inline filters/search inputs often rely only on placeholders. Add visible labels or visually-hidden labels.
- Error messages should be associated with fields and announced via `role="alert"` where appropriate.

## 8. Responsive findings

- Application sidebar is hidden on screens below `lg`, with no mobile navigation replacement. Authenticated mobile users lose primary navigation.
- `IncidentQueueTable` uses `min-w-[980px]`, so mobile/tablet users get horizontal overflow instead of an adapted list/card view.
- Incident detail has a two-column case workspace and sticky right rail. It collapses via grid, but the page itself is outside `MainLayout` and uses fixed `p-6`, which may feel cramped on small screens.
- Export detail drawer uses `w-full max-w-2xl`; on mobile it becomes full width but lacks mobile header/footer affordances and focus trapping.
- Login form is centered and responsive enough but visually generic.
- Marketing resource pages are responsive separately, but app document center requirements should not reuse marketing carousel patterns unchanged.

## 9. Loading, empty, error, and success state findings

- Loading states vary between plain text (`Loading…`, `Loading exports…`, `Loading incident queue…`) and skeleton components.
- Error states vary between red text, red banners, and centered full-screen messages.
- Empty states vary between plain muted text and `EmptyStateCard`.
- Success states are often green panels or inline text; no consistent success confirmation primitive exists.
- Incident detail loading/error states are outside the shell, which creates a jarring transition.
- Recommendation: standardize `PageSkeleton`, `Alert`, `EmptyState`, and optional `Toast` after the core primitives land.

## 10. Highest-priority visual problems

1. **Incident detail is not inside the authenticated application shell**, so it looks like a separate app and loses global navigation/context.
2. **Login has a generic Tailwind/dark-mode look** that does not match the desired calm, premium B2B SaaS direction.
3. **Raw/short technical IDs are too prominent** in case, queue, owner, export, and drawer views.
4. **Too many competing actions and statuses appear at once**, especially dashboard queue rows, incident right rail, and export list/drawer.
5. **Hardcoded raw Tailwind colors overpower the semantic token system**, fragmenting the product personality.
6. **Status color usage is overly saturated and inconsistent**, creating urgency noise rather than prioritization.
7. **Tables are dense and not mobile-friendly**, especially the command-center incident queue.
8. **Modal/drawer accessibility is incomplete**, especially export detail and generate export flows.

## 11. Proposed design direction

### Product personality translation

- **Calm:** neutral gray canvas, white surfaces, subtle borders, minimal shadow, no decorative gradients or playful motion.
- **Trustworthy:** predictable layout, restrained blue primary action, clear audit/export metadata, visible timestamps, stable typography.
- **Decisive:** one dominant next action per surface; secondary actions visually quiet; urgency represented through priority order and concise labels.
- **Operational:** dense enough for case work but organized into clear zones: overview, queue, evidence, tasks, export readiness.
- **Modern/professional:** consistent spacing, system/Inter typography, semantic tokens, and polished empty/loading/error states.

### Page-level redesign principles

- Use a neutral canvas (`color.background.canvas`) and white content surfaces.
- Promote human-readable case summaries over IDs.
- Use status colors as accents, not full panels, unless the state is critical.
- Reduce global quick actions to one primary and one secondary action based on route context.
- Keep tables for desktop operators but provide responsive row cards for narrow screens.
- Use `PageHeader` for page identity and `Card`/`DataTable` for content grouping.
- Treat export/document detail as a right-side drawer with legal-grade metadata hierarchy.

## 12. Proposed semantic token system

### Color tokens

```ts
color.background.canvas       // app canvas, neutral gray
color.background.shell        // sidebar/top shell, dark restrained navy or white shell variant
color.background.surface      // primary white surface
color.background.subtle       // subtle gray section background
color.background.raised       // elevated surface, still white
color.background.overlay      // modal/drawer backdrop

color.text.primary            // high-emphasis text
color.text.secondary          // supporting text
color.text.muted              // low-emphasis labels
color.text.inverse            // text on dark shell
color.text.disabled           // disabled controls

color.border.default          // standard card/control border
color.border.subtle           // dividers
color.border.strong           // selected/active border
color.border.focus            // focus ring color

color.action.primary          // one primary blue
color.action.primaryHover
color.action.primarySoft
color.action.secondary
color.action.danger

color.status.info
color.status.infoSoft
color.status.success
color.status.successSoft
color.status.warning
color.status.warningSoft
color.status.critical
color.status.criticalSoft
color.status.neutral
color.status.neutralSoft
```

### Spacing tokens

```ts
spacing.0  = 0
spacing.1  = 0.25rem
spacing.2  = 0.5rem
spacing.3  = 0.75rem
spacing.4  = 1rem
spacing.5  = 1.25rem
spacing.6  = 1.5rem
spacing.8  = 2rem
spacing.10 = 2.5rem
spacing.12 = 3rem
```

### Radius tokens

```ts
radius.none
radius.sm   // compact controls
radius.md   // default controls
radius.lg   // cards
radius.xl   // hero/dialog surfaces only
radius.full // pills/avatar
```

### Elevation tokens

```ts
shadow.none
shadow.sm      // subtle card lift
shadow.md      // popover/dropdown
shadow.lg      // modal/drawer only
shadow.focus   // focus ring shadow if needed
```

### Typography tokens

```ts
font.family.sans
font.family.mono

type.display.sm
type.heading.xl
type.heading.lg
type.heading.md
type.body.md
type.body.sm
type.label.md
type.label.sm
type.caption
type.code
```

### Control tokens

```ts
control.height.sm = 2rem
control.height.md = 2.5rem
control.height.lg = 3rem
control.padding.x.sm/md/lg
control.icon.sm = 1rem
control.icon.md = 1.25rem
control.icon.lg = 1.5rem
control.focusRing
transition.duration.fast = 120ms
transition.duration.base = 180ms
transition.duration.slow = 240ms
```

## 13. Recommended component architecture

### Proposed folder shape

```txt
frontend/components/ui/
  Alert.tsx
  Badge.tsx
  Breadcrumbs.tsx
  Button.tsx
  Card.tsx
  DataTable.tsx
  Drawer.tsx
  EmptyState.tsx
  FormField.tsx
  IconButton.tsx
  MetricCard.tsx
  Modal.tsx
  PageHeader.tsx
  ProgressBar.tsx
  Skeleton.tsx
  StatusBadge.tsx
  Tabs.tsx

frontend/components/app-shell/
  AppShell.tsx
  AppSidebar.tsx
  AppTopbar.tsx
  MobileNav.tsx
  RouteBreadcrumbs.tsx

frontend/components/case-ops/
  // domain-specific composition only; no raw visual styling except layout glue

frontend/lib/design/
  tokens.ts
  variants.ts
  statusTones.ts
```

### Component rules

- Domain components should compose `ui/*` primitives instead of hardcoding buttons/cards/badges.
- Keep `lib/status` as domain metadata, but map statuses to semantic UI tones in one place.
- Keep native form controls initially; do not add a headless UI library unless focus management becomes too costly.
- If adding a dependency, prefer a tiny focused utility for focus trapping/dialog accessibility rather than a broad component kit.
- Maintain compatibility re-export shims during migration, then remove once imports are updated.

## 14. Proposed phased implementation sequence

### Phase 1 — Design foundation and primitive consolidation

- Finalize semantic tokens in `frontend/app/globals.css` and `frontend/lib/design/tokens.ts`.
- Add `frontend/components/ui/Button.tsx`, `Card.tsx`, `Badge.tsx`, `StatusBadge.tsx`, `FormField.tsx`, `Alert.tsx`, `EmptyState.tsx`, and `Skeleton.tsx`.
- Add shared focus styles and control heights.
- Migrate only low-risk existing data-display/layout components to consume primitives.

Likely files to change:

- `frontend/app/globals.css`
- `frontend/lib/design/tokens.ts`
- `frontend/lib/status/index.ts`
- `frontend/components/ui/*`
- `frontend/components/layout/PageHeader.tsx`
- `frontend/components/layout/SectionCard.tsx`
- `frontend/components/data-display/*`

### Phase 2 — Login and application shell

- Redesign `/login` with app tokens, brand hierarchy, demo sandbox alert, and shared form/button primitives.
- Split `MainLayout` into shell/sidebar/topbar/breadcrumb/mobile nav pieces.
- Add mobile navigation.
- Reduce global quick actions and make route-specific actions part of `PageHeader`.
- Stop showing raw org/user IDs as primary shell content.

Likely files to change:

- `frontend/app/login/page.tsx`
- `frontend/components/layout/MainLayout.tsx`
- `frontend/components/MainLayout.tsx`
- `frontend/components/app-shell/*`
- `frontend/components/ui/Breadcrumbs.tsx`
- `frontend/lib/permissions.ts`
- tests covering demo login/shell render states

### Phase 3 — Command Center dashboard

- Rework dashboard into a calm command center: top page header, compact metrics, priority queue, side panels for alerts/export-ready items.
- Convert queue tabs to `SegmentedControl`/`Tabs`.
- Convert queue to `DataTable` with accessible label/caption and mobile row card fallback.
- Reduce row actions to a primary `Open` plus overflow/secondary controls.
- Promote human-readable vehicle/driver/case summary.

Likely files to change:

- `frontend/app/dashboard/DashboardClient.tsx`
- `frontend/components/case-ops/IncidentQueueTable.tsx`
- `frontend/components/case-ops/IncidentFilterBar.tsx`
- `frontend/components/case-ops/IncidentSummaryCards.tsx`
- `frontend/components/case-ops/AlertsPanel.tsx`
- `frontend/components/case-ops/ExportReadyList.tsx`
- `frontend/components/case-ops/OverdueFollowUpList.tsx`
- `frontend/components/ui/DataTable.tsx`
- `frontend/components/ui/Tabs.tsx`

### Phase 4 — Incident detail workspace

- Wrap incident detail in the application shell.
- Replace `CaseHeroHeader` with `PageHeader`/`CaseHeader` showing human-readable case context and one next action.
- Convert evidence/weather/timeline/tasks/notes/readiness/export panels to `Card`, `StatusBadge`, `ProgressBar`, `Alert`, and `Button`.
- Prioritize right rail: owner/status/readiness/next action; move less-critical metadata lower.
- Standardize loading/error states inside shell.

Likely files to change:

- `frontend/app/incidents/[id]/page.tsx`
- `frontend/app/incidents/[id]/IncidentDetailClient.tsx`
- `frontend/components/case-ops/CaseHeroHeader.tsx`
- `frontend/components/case-ops/EvidenceStatusPanel.tsx`
- `frontend/components/case-ops/TimelineFeed.tsx`
- `frontend/components/case-ops/CaseTasksPanel.tsx`
- `frontend/components/case-ops/CaseNotesPanel.tsx`
- `frontend/components/case-ops/CaseOwnerControl.tsx`
- `frontend/components/case-ops/CaseStatusControl.tsx`
- `frontend/components/case-ops/CaseReadinessCard.tsx`
- `frontend/components/case-ops/MissingItemsPanel.tsx`
- `frontend/components/Timeline.tsx`
- `frontend/components/EvidenceTable.tsx`
- `frontend/components/IncidentDetailExportPanel.tsx`

### Phase 5 — Exports and documents

- Replace local exports header/count cards/filter bar with `PageHeader`, `MetricCard`, and `Card`.
- Replace export detail overlay with shared `Drawer` using accessible dialog semantics.
- Make export rows human-readable: packet type, incident label, created/completed timestamps, readiness/integrity status; move UUID/SHA to metadata.
- Convert generate export flow to shared `Modal`.
- Create an authenticated documents/export resources pattern separate from marketing resource pages if needed.

Likely files to change:

- `frontend/app/exports/page.tsx`
- `frontend/components/exports/ExportListItem.tsx`
- `frontend/components/exports/ExportPanel.tsx`
- `frontend/components/exports/IncidentDetailExportPanel.tsx`
- `frontend/components/exports/GenerateExportModal.tsx`
- `frontend/components/ui/Drawer.tsx`
- `frontend/components/ui/Modal.tsx`
- `frontend/app/resources/docs/page.tsx`
- `frontend/app/resources/sample-documents/page.tsx`

### Phase 6 — Secondary surfaces and cleanup

- Apply primitives to onboarding, integrations, imports, reports, vehicles, admin pages.
- Remove compatibility re-export shims once imports converge.
- Add visual regression screenshots for demo-critical flows if available.
- Add accessibility checks for tables/dialogs/forms.

Likely files to change:

- `frontend/components/onboarding/*`
- `frontend/components/integrations/*`
- `frontend/components/imports/*`
- `frontend/components/reports/*`
- `frontend/app/vehicles/page.tsx`
- `frontend/app/admin/vehicles/page.tsx`
- `frontend/app/admin/ops/*`
- top-level re-export shims under `frontend/components/*`

## 15. Risks and regression areas

- **Auth and role-based navigation:** shell refactors could accidentally expose or hide routes incorrectly. Keep nav capability checks covered.
- **Demo login behavior:** `/login?demo=1` must continue respecting non-production env-only prefill behavior.
- **Incident workflow:** queue actions, owner assignment, status changes, notes/tasks, refresh loop, and export generation must remain behaviorally unchanged.
- **Export security:** `safeOpenDownloadUrl`, retry/download/detail flows, and blocked-host messaging must remain unchanged.
- **Responsive navigation:** adding mobile nav must not break desktop keyboard navigation.
- **Accessibility/focus management:** modal/drawer refactors need focus trap and return-focus behavior without blocking keyboard users.
- **Token migration:** changing CSS variable names can silently break many Tailwind classes. Migrate aliases gradually and keep old names until all usage is moved.
- **Marketing vs app styling:** marketing pages use their own token file; avoid accidentally redesigning marketing in app-focused phases unless explicitly planned.

## 16. Validation plan for Phase 0

Phase 0 created documentation only and should not modify runtime behavior. Validation should confirm no frontend source behavior changed and repository tests that inspect key frontend render/build assumptions still pass.

Recommended minimal checks:

```bash
git diff -- frontend/app frontend/components frontend/lib frontend/package.json frontend/package-lock.json
cd frontend && npm test
```

Because no runtime code changed, full backend lint/type/tests are unnecessary for this audit-only phase unless repository policy requires them for every change regardless of scope.
