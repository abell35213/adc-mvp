import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import { buildPageMetadata } from "../../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "Blog | ADC Resources",
  "Read the latest ADC insights on fleet safety, claims defense, and compliance operations.",
  "/resources/blog",
);

export default function BlogPage() {
  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
      <h1 className="text-3xl font-bold">Blog</h1>
      <p className="max-w-3xl text-slate-700">
        Practical guidance from operators and subject-matter experts across safety, claims, and compliance.
      </p>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          "Incident response checklist for first 24 hours",
          "How audit trails accelerate insurer collaboration",
          "Leading indicators for safer driver behavior",
        ].map((post) => (
          <article key={post} className="rounded-lg border border-slate-200 p-4">{post}</article>
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        <TrackedCta href="/resources/blog" label="Read latest insights" location="blog-primary" />
        <TrackedCta
          href="/resources"
          label="Subscribe newsletter"
          location="blog-secondary"
          className="inline-flex rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
        />
      </div>
    </main>
  );
}
