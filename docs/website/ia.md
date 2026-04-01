# Website Information Architecture (IA) Spec

This document defines the public website IA for ADC MVP, including page-level goals, conversion actions, audience focus, and trust/proof requirements.

## Global principles

- **Primary conversion goal:** Drive qualified demo/contact requests from fleet decision-makers.
- **Secondary conversion goals:** Encourage self-education (docs/resources), nurture via case studies/blog, and support recruiting.
- **Proof-first messaging:** Every high-intent page should include concrete proof points (metrics, artifacts, customer evidence, or compliance indicators).

## Page-level IA requirements

| Page | Route | Primary CTA | Secondary CTA | Target persona | Required proof points |
|---|---|---|---|---|---|
| Home | `/` | **Book a demo** | **View platform** | Mixed buying committee: Safety Director, Risk/Claims Lead, Operations Executive | Hero value proposition; customer logos; 2-3 quantified outcomes (e.g., claim reduction, faster incident resolution); short product walkthrough; testimonial quote with name/title/company |
| Product overview | `/product` | **Start product tour** | **Talk to sales** | Evaluation-stage buyer (Safety/Risk leader) comparing vendors | Clear problem-solution map; capability summary by workflow; integration list; before/after operational impact; security/compliance posture summary |
| Solutions: Fleet Safety | `/solutions/fleet-safety` | **Improve driver safety** | **See safety playbook** | Safety Director / Fleet Safety Manager | Safety KPI impact (incident frequency, coaching completion); workflow example; driver adoption indicators; customer mini-case with measurable outcomes |
| Solutions: Claims Defense | `/solutions/claims-defense` | **Defend claims faster** | **View evidence workflow** | Claims Manager / Risk Manager / General Counsel stakeholder | Time-to-evidence benchmarks; chain-of-custody explanation; export/legal packet example; outcome metrics (faster closure, reduced payouts); testimonial from claims/risk function |
| Solutions: Compliance | `/solutions/compliance` | **Automate compliance** | **Explore compliance checklist** | Compliance Manager / Safety & Compliance Officer | Supported regulatory frameworks checklist; audit-readiness artifacts; exception/alert reporting examples; proof of retention and policy controls |
| Platform | `/platform` | **Explore platform** | **See all features** | Technical evaluator + business owner | Platform architecture overview; module map; role-based access model; integration/API surface; reliability/security snapshot |
| Feature: Evidence Vault | `/platform/evidence-vault` | **See Evidence Vault demo** | **Download sample export** | Claims/Risk and legal operations users | Immutable evidence handling details; retention policy controls; tamper-evidence/audit log explanation; export artifacts preview |
| Feature: Driver Protocol | `/platform/driver-protocol` | **See Driver Protocol flow** | **View driver experience** | Safety manager and driver operations lead | Driver UX steps; completion/adherence rates; multilingual/accessibility support (if available); coaching workflow outcomes |
| Feature: Exports | `/platform/exports` | **Generate compliant exports** | **View export formats** | Claims analysts, compliance, legal ops | Supported export formats/channels; legal/insurer-ready packet examples; SLA/turnaround benchmarks; audit trail for export actions |
| Pricing | `/pricing` | **Request pricing** | **Compare plans** | Budget owner + procurement + operations sponsor | Transparent packaging logic; inclusions/exclusions; ROI model inputs; implementation/support scope; procurement/security review readiness |
| Resources hub | `/resources` | **Browse resources** | **Subscribe for updates** | Mid-funnel researchers across safety/risk/compliance | Content taxonomy by use case; featured case studies/blog/docs; freshness indicators (dates/authors); trust signals (expert contributors) |
| Resources: Case Studies | `/resources/case-studies` | **Read case study** | **Book a similar assessment** | Decision-stage buyer seeking peer validation | Industry/company context; baseline vs outcome metrics; deployment timeline; named quote/approval where possible |
| Resources: Blog | `/resources/blog` | **Read latest insights** | **Subscribe newsletter** | Early- to mid-funnel practitioners | Author credentials; publication dates; citations/data sources; actionable frameworks/checklists |
| Resources: Docs | `/resources/docs` | **Open documentation** | **Contact support/sales engineer** | Technical evaluator, implementation lead, admin users | Quickstart clarity; API/integration references; versioning/changelog visibility; troubleshooting depth |
| Company hub | `/company` | **About ADC** | **Contact us** | Trust-validation visitors: buyers, partners, candidates | Mission and positioning; leadership snapshot; office/contact basics; links to careers and legal |
| Company: About | `/company/about` | **Meet the team** | **View careers** | Buyers and candidates validating credibility | Leadership bios; company milestones; customer/partner ecosystem; media/press references |
| Company: Contact | `/company/contact` | **Submit contact form** | **Book a meeting** | Inbound prospects, partners, support seekers | Response-time expectation; routing options (sales/support/partnerships); direct channels; privacy notice near form |
| Company: Careers | `/company/careers` | **View open roles** | **Join talent network** | Prospective employees | Open positions with location/type; hiring process overview; culture/benefits highlights; DEI/equal opportunity statement |
| Legal: Privacy | `/privacy` | **Review privacy policy** | **Contact privacy team** | Legal/procurement reviewers and end users | Data categories collected; processing purposes; retention policy; rights/request process; effective date + update history |
| Legal: Terms | `/terms` | **Review terms of service** | **Contact legal** | Legal/procurement reviewers | Service terms scope; acceptable use; limitation/liability structure; termination terms; governing law and effective date |

## Navigation structure

- **Primary nav:** Product, Solutions, Platform, Pricing, Resources, Company
- **Utility nav:** Docs, Contact, Book demo
- **Footer nav:** Solutions pages, Platform feature pages, Resources pages, Company pages, Legal pages

## CTA normalization (recommended labels)

To keep conversion tracking consistent across templates:

- Demo-oriented: **Book a demo**, **See demo**, **Talk to sales**
- Education-oriented: **View docs**, **Read case study**, **See playbook**
- Trust/legal-oriented: **Contact legal**, **Contact privacy team**

## Proof point quality bar

Each page should include at least **two** of the following proof types (high-intent pages should include **three or more**):

1. Quantified customer outcomes (percentage/time/cost impact).
2. Named customer evidence (logo, quote, case study).
3. Artifact-level proof (sample export, workflow diagram, checklist).
4. Governance proof (security/privacy/compliance statements).
5. Operational proof (implementation timeline, support SLA, uptime/reliability stats).

## IA implementation status (updated April 1, 2026)

All routes listed in this IA are now represented in `frontend/app/` and can be safely linked from primary navigation, utility navigation, and footer navigation.
