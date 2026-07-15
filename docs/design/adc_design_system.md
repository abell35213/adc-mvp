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
