# ADC Application Shell

## 1. Shell architecture
`frontend/components/app-shell` contains the shared authenticated shell: `AppShell`, `Sidebar`, `MobileNavigation`, `TopBar`, `UserMenu`, `NavigationItem`, navigation helpers, and `PageContainer`. Existing `MainLayout` and `AdminLayout` now delegate to this shell so pages keep their imports while visual systems converge.

## 2. Desktop navigation
The desktop sidebar is 16rem wide and uses restrained ADC identity: `ADC` and `Accident Defense Center`. It is split into primary and secondary navigation areas.

## 3. Mobile navigation
Mobile uses the shared `Drawer` primitive. The trigger has an accessible name, the drawer has dialog semantics, a named close button, focus containment, Escape close, focus return, body-scroll lock, active-route indication, and the global Create Incident action.

## 4. Active-state rules
Active navigation uses a subtle lighter shell background, strong white label text, and a modest left indicator. Hover and keyboard focus are separate treatments, with focus-visible rings that do not depend on color alone.

## 5. Organization context
The shell displays a human-readable organization label. Raw UUID-like organization identifiers are replaced with `Primary organization` so UUIDs are not the primary visible tenant context.

## 6. Page-container behavior
`PageContainer` provides the `main` landmark, skip-link target, responsive padding, canvas spacing, and full-width support for operational tables on dashboard, cases, and exports routes. It avoids forcing every operational page into a narrow marketing max width.

## 7. Top-bar action hierarchy
The top bar shows breadcrumbs/page context, mobile navigation trigger, Help, one primary Create Incident action, and the user menu. Contextual actions remain inside page-specific headers or sections.

## 8. User-menu behavior
The user menu uses menu semantics, exposes user/account and organization context, supports Escape close, closes on outside click, returns focus to the trigger, and preserves the existing sign-out API behavior.

## 9. Login design
The login page uses a restrained neutral canvas, ADC product identity, concise value statement, `Card`, `FormField`, `Input`, `Button`, and `Alert`. Errors are user-facing and sanitized.

## 10. Demo-entry behavior
`/login?demo=1` remains supported only when non-production demo public environment variables are configured. Demo copy explains that the prefilled account enters a prepared workspace and uses `Enter Demo Workspace` as the action label. Production builds do not expose fallback credentials.

## 11. Accessibility requirements
The shell requires skip-to-content, semantic `header`/`nav`/`main` landmarks, current-page indication, visible focus, accessible icon buttons, correct dialog semantics, keyboard-operable drawer/menu interactions, and status/error text that is not color-only.

## 12. Remaining legacy layout migration work
Later phases should migrate legacy page headers, dense dashboard cards, incident workspace sections, export drawers, business admin forms, and one-off operational buttons/cards into the Phase 1 primitives. Compatibility re-export files remain until all imports converge.
