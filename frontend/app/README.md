# UI Design Contract (Sprints 1–5)

This document is the engineering-facing design contract for all UI work in **Sprints 1–5**.
It is a **review gate** for every UI PR touching `frontend/app/**` and related `frontend/components/**` surfaces.

## 1) Product objective language (required in UX copy and reviews)

Design and copy should make operators successful at:

- **Incident attention:** what needs action now vs. what can wait.
- **Evidence captured / missing:** what is present, what is incomplete, and what blocks case readiness.
- **Export readiness:** whether a case can be exported confidently and why/why not.
- **Owner:** who is currently responsible for the case.
- **Next action:** the single clearest next operator move.

When in doubt, bias toward language that reduces ambiguity and clarifies operational state.

## 2) App feel rules

The application should feel like a:

1. **Command center** on list/queue pages (triage, prioritize, monitor).
2. **Case workspace** on incident detail pages (investigate, coordinate, resolve).
3. **Evidence-readiness workflow** on export and readiness surfaces (verify completeness, unblock missing items).

Practical implications:

- Prioritize hierarchy that makes status and urgency scannable in <5 seconds.
- Keep primary actions visible and stable across similar pages.
- Preserve context while drilling into details (avoid disorienting transitions).

## 3) Anti-patterns to avoid

Do **not** ship UI that looks or behaves like:

- A generic CRUD back office with no urgency or state semantics.
- Table-only experiences with no readiness narrative.
- A generic "admin panel" aesthetic for case operations workflows.

Red flags in PR review:

- Critical status only appears inside dense tables.
- No explicit representation of missing evidence or blockers.
- No clear owner or next-action cue on operational pages.

## 4) Visual direction rules

Core direction for Sprints 1–5:

- **Dark shell** for global chrome/navigation.
- **Light surfaces** for primary content work areas.
- **Semantic status colors** used consistently for state:
  - Success / ready
  - Warning / needs attention
  - Critical / blocked or overdue
  - Neutral / informational

Rules:

- Never rely on color alone; pair with labels/icons/text.
- Keep status color meanings consistent across all pages/components.
- Maintain contrast/accessibility for dark-shell and light-surface pairings.

## 5) UI PR review gate (Sprints 1–5)

A UI PR is not review-ready until each applicable item below is checked.

### Global checklist (applies to every UI PR)

- [ ] Product objective language is present where relevant (attention, evidence status, export readiness, owner, next action).
- [ ] App feel matches intended mode (command center, case workspace, or evidence readiness).
- [ ] Anti-patterns are avoided (not generic CRUD/table-only/admin look).
- [ ] Visual direction is respected (dark shell + light surfaces + semantic statuses).
- [ ] Status meaning remains consistent with existing patterns.

### Major page acceptance checklist

| Page / Surface | Required acceptance criteria |
| --- | --- |
| `/dashboard` | Queue/summary views emphasize incident attention; highlight owner and next action for high-priority work. |
| `/incidents` | Triage state is immediately scannable; missing evidence and readiness blockers are explicit. |
| `/incidents/[id]` | Page operates as a case workspace with clear ownership, evidence captured vs missing, and concrete next actions. |
| `/exports` | Export readiness is explicit per case; blockers and remediation paths are visible before export actions. |
| `/timeline` | Timeline reinforces operational attention and progression toward evidence completeness/readiness. |
| `/reports` | Reporting emphasizes operational outcomes (attention, readiness, unresolved blockers), not just raw counts. |
| `/settings/integrations` | Integration health clearly connects to evidence capture risk and downstream export readiness. |
| `/onboarding` and onboarding sub-pages | Readiness progression is explicit; each step clarifies ownership and next action to reach go-live readiness. |
| `/admin/ops` and key ops sub-pages | Operational tooling supports command-center behavior; avoid generic back-office presentation. |

## 6) Enforcement

- Treat this document as the **design contract** for Sprints 1–5.
- UI PR templates/reviews should link to this file and mark checklist completion.
- If a PR intentionally deviates, include a short rationale and design sign-off in the PR description.

## 24) Definition of Done release gate (visual + functional + responsive + accessibility)

Every UI task introducing or updating reusable components must include a QA report stored in `frontend/docs/` (or this file) that records results for:

- Visual contract checks (dark shell / light surfaces / semantic statuses / anti-pattern avoidance).
- Functional checks (loading, empty, and error behavior; operator next action clarity).
- Responsive checks:
  - Desktop: dual-column rails.
  - Tablet: stacked rails, wrapped filters, horizontal table scroll.
  - Mobile: KPI carousel behavior, table-to-card transforms, filter drawer affordance.
- Accessibility checks (semantic landmarks, keyboard navigation, contrast, screen-reader announcements, and non-color status cues).

A UI PR is **not done** until this checklist is completed and linked in the PR description.
