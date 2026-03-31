# Website Launch Checklist

Use this checklist before publishing any major website update (new pages, messaging updates, or campaign-driven landing pages).

## 1) Copy review workflow

- [ ] **Product review complete**
  - [ ] Product marketing confirms message hierarchy (headline, subhead, CTA alignment).
  - [ ] Product owner verifies feature claims against current roadmap and shipped behavior.
  - [ ] Any metrics or outcome claims have a source of truth documented.
- [ ] **Legal review complete**
  - [ ] Counsel reviews all statements that imply guarantees, legal outcomes, or contractual obligations.
  - [ ] Required disclaimers are present near sensitive claims (results, guarantees, legal/compliance language).
  - [ ] Privacy and terms links are visible and up to date.
- [ ] **Compliance review complete**
  - [ ] Compliance owner signs off on regulatory references and terminology.
  - [ ] Data handling/storage language matches current internal policies.
  - [ ] Retention, auditability, and governance claims are accurate.
- [ ] **Final sign-off recorded**
  - [ ] Approvals from product, legal, and compliance are captured in the release tracker.
  - [ ] Version/date of approved copy is noted for audit trail.

## 2) Asset checklist

- [ ] **Brand assets**
  - [ ] Correct, current logo files are used (light/dark/background variants as needed).
  - [ ] Favicon and social share images are updated and render correctly.
- [ ] **Customer proof assets**
  - [ ] Customer logos have explicit usage approval.
  - [ ] Customer quotes include approved wording, attribution, and title/company.
  - [ ] Case-study links are valid and point to the intended story.
- [ ] **Product visuals**
  - [ ] Screenshots reflect the current UI and current terminology.
  - [ ] Sensitive data in screenshots is redacted or replaced with demo data.
  - [ ] Image dimensions and crops are consistent across breakpoints.
- [ ] **File quality and rights**
  - [ ] All assets are licensed/owned for commercial use.
  - [ ] Source files are stored in the shared repository/location for future edits.

## 3) Technical checks

- [ ] **Broken-link sweep**
  - [ ] Run a link checker across edited pages.
  - [ ] Validate internal anchors and footer/legal links manually.
- [ ] **Form submission path**
  - [ ] Confirm form submits in production/staging context.
  - [ ] Confirm success and error states render correctly.
  - [ ] Confirm submissions land in the expected CRM/inbox/automation destination.
  - [ ] Confirm spam protection and rate limits are functioning.
- [ ] **Metadata completeness**
  - [ ] Every launch page has unique title and meta description.
  - [ ] Open Graph and Twitter metadata include title, description, canonical URL, and image.
  - [ ] Canonical tags and robots directives are correct for indexable pages.
- [ ] **Accessibility spot checks**
  - [ ] Verify heading order and landmark structure.
  - [ ] Verify keyboard navigation for nav, forms, and modal/dialog flows.
  - [ ] Verify visible focus states and sufficient color contrast.
  - [ ] Verify form fields have labels, helper/error text, and accessible names.
  - [ ] Verify images include meaningful alt text (or empty alt for decorative images).

## 4) Performance targets and image optimization rules

### Performance targets (minimum launch bar)

- [ ] Largest Contentful Paint (LCP): **<= 2.5s** on key landing pages.
- [ ] Interaction to Next Paint (INP): **<= 200ms**.
- [ ] Cumulative Layout Shift (CLS): **<= 0.10**.
- [ ] Initial JavaScript budget for critical pages stays within agreed team threshold.

### Image optimization rules

- [ ] Use modern formats first (WebP/AVIF) with fallback only when required.
- [ ] Resize images to displayed dimensions; avoid serving oversized originals.
- [ ] Provide responsive variants (`srcset`/sizes) for major breakpoints.
- [ ] Compress aggressively without visible quality loss.
- [ ] Lazy-load non-critical images below the fold.
- [ ] Define width/height (or aspect ratio) to prevent layout shift.
- [ ] Keep hero image weight tightly controlled; avoid text baked into raster images when possible.

## 5) Post-launch validation steps

- [ ] **Analytics validation**
  - [ ] Confirm page-view events fire on all launched/edited pages.
  - [ ] Confirm CTA click events fire with correct labels/properties.
  - [ ] Confirm form-start and form-submit events fire once per interaction.
  - [ ] Confirm analytics data appears in dashboard/reporting destination.
- [ ] **Conversion path smoke checks**
  - [ ] Execute the primary conversion flow end-to-end as a new user.
  - [ ] Verify confirmation page/email and any downstream automation.
  - [ ] Verify routing to sales/support owners and SLA expectations.
  - [ ] Test on desktop and mobile breakpoints.
- [ ] **Launch monitoring window (first 24-72 hours)**
  - [ ] Monitor error rates, bounce anomalies, and conversion drop-offs.
  - [ ] Monitor key page performance for regressions.
  - [ ] Log any hotfixes and update this checklist if recurring issues are found.

---

## Sign-off summary

- Launch owner:
- Launch date:
- Product approver:
- Legal approver:
- Compliance approver:
- Analytics validation completed by:
- Notes / follow-ups:
