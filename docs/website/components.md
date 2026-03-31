# Website marketing components

The marketing UI lives in:

- `frontend/app/(marketing)/marketing/page.tsx`
- `frontend/components/marketing/*`

## Brand tokens

Shared tokens are defined in `frontend/components/marketing/tokens.ts`.

- **Spacing:** `container`, `sectionSpacing`
- **Typography:** `headingScale.display`, `h2`, `h3`, `body`, `muted`
- **Buttons:** `buttonVariants.primary`, `buttonVariants.secondary`
- **Surfaces:** `surfaces.page`, `card`, `subtle`, `accent`

Use these tokens in new marketing sections to preserve visual consistency and responsive behavior.

## Layout primitives

- `MarketingContainer`: enforces the canonical max-width and horizontal padding.
- `MarketingSection`: wraps section spacing and container behavior.

Prefer these instead of manual `max-w-*` wrappers.

## Reusable sections

- `Hero`
  - Includes top navigation with keyboard focus styles.
  - Includes accessible form labels and submit action.
- `ProofBar`
  - Lightweight proof-point row with responsive grid behavior.
- `FeatureGrid`
  - Feature cards, section heading, and descriptive lead text.
- `UseCaseCards`
  - Role-based use case cards for claims/safety/compliance.
- `TestimonialQuote`
  - Featured customer quote surface.
- `PricingTable`
  - Tier cards with ARIA labels and strong CTA affordance.
- `CTASection`
  - End-of-page conversion call-to-action.

## Accessibility standards

For all marketing components:

1. Include `focus-visible` ring styles on links/buttons/inputs.
2. Provide `aria-label` text where action context is ambiguous.
3. Keep form controls associated with `<label>` elements.
4. Maintain contrast by using slate/sky palette combinations already in tokens.
5. Use semantic landmarks (`header`, `nav`, `section`, `main`) and heading hierarchy.
