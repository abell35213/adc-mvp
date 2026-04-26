"use client";

import { useState } from "react";
import MainLayout from "@/components/MainLayout";
import HelpArticleCard, { type HelpArticle } from "@/components/support/HelpArticleCard";

type HelpCategoryKey = "getting_started" | "incident_ops" | "exports";

const CATEGORY_TABS: Array<{ key: HelpCategoryKey; label: string }> = [
  { key: "getting_started", label: "Getting started" },
  { key: "incident_ops", label: "Incident operations" },
  { key: "exports", label: "Exports & readiness" },
];

const ARTICLE_MAP: Record<HelpCategoryKey, HelpArticle[]> = {
  getting_started: [
    {
      title: "Launch checklist for new operators",
      href: "/onboarding",
      description: "Walk through ownership, evidence capture setup, and first-response workflows before go-live.",
      readTime: "6 min read",
      audience: "Ops leads",
    },
    {
      title: "Configure team roles and assignment rules",
      href: "/settings/integrations",
      description: "Set owner routing so every incident gets a clear accountable responder.",
      readTime: "5 min read",
      audience: "Admins",
    },
  ],
  incident_ops: [
    {
      title: "Triage queue best practices",
      href: "/incidents",
      description: "Prioritize incident attention and reduce unresolved blocker carry-over between shifts.",
      readTime: "7 min read",
      audience: "Dispatch",
    },
    {
      title: "How to chase missing evidence quickly",
      href: "/timeline",
      description: "Use timeline checkpoints to detect capture gaps and trigger next actions within SLA windows.",
      readTime: "4 min read",
      audience: "Investigators",
    },
  ],
  exports: [
    {
      title: "Export readiness playbook",
      href: "/exports",
      description: "Validate package completeness, resolve blockers, and prepare legal-ready deliverables.",
      readTime: "8 min read",
      audience: "Compliance",
    },
    {
      title: "When to escalate blocked export cases",
      href: "/trust",
      description: "Identify policy-based blockers and collect evidence required for trust and audit teams.",
      readTime: "5 min read",
      audience: "Legal ops",
    },
  ],
};

const FEATURED_ARTICLES = [
  "What changed in readiness scoring this month",
  "Incident owner handoff template",
  "Evidence retention FAQ",
];

const RELATED_TOPICS = ["Trust Center", "Deployment coverage", "Integration health", "Admin ops runbooks"];

export default function HelpPage() {
  const [activeCategory, setActiveCategory] = useState<HelpCategoryKey>("getting_started");
  const articles = ARTICLE_MAP[activeCategory];

  return (
    <MainLayout title="Help Center">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <section className="space-y-4">
          <article className="rounded-lg border border-border-default bg-surface p-4 shadow-card">
            <h2 className="text-xl font-semibold text-text-primary">Operator help center</h2>
            <p className="mt-1 text-sm text-text-secondary">
              Find focused guidance by workflow stage, then take the clearest next action.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {CATEGORY_TABS.map((tab) => {
                const active = activeCategory === tab.key;
                return (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => setActiveCategory(tab.key)}
                    className={[
                      "rounded-md px-3 py-1.5 text-sm font-medium transition",
                      active
                        ? "bg-status-info-soft text-status-info"
                        : "border border-border-subtle text-text-secondary hover:bg-surface-raised",
                    ].join(" ")}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </article>

          <div className="space-y-3">
            {articles.map((article) => (
              <HelpArticleCard key={article.href} article={article} />
            ))}
          </div>
        </section>

        <aside className="space-y-4">
          <section className="rounded-lg border border-border-subtle bg-surface p-4 shadow-card">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-text-muted">Featured</h3>
            <ul className="mt-3 space-y-2 text-sm text-text-secondary">
              {FEATURED_ARTICLES.map((item) => (
                <li key={item} className="rounded-md border border-border-subtle bg-surface-raised px-3 py-2">
                  {item}
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-lg border border-border-subtle bg-surface p-4 shadow-card">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-text-muted">Related topics</h3>
            <ul className="mt-3 space-y-2 text-sm text-text-secondary">
              {RELATED_TOPICS.map((item) => (
                <li key={item} className="rounded-md border border-border-subtle px-3 py-2">
                  {item}
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </MainLayout>
  );
}
